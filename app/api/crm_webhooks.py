import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings
from app.memory.session import get_or_create_lead, update_lead_field
from app.models.lead import CourseSlug, LeadStage
from app.script.engine import run_script_step

logger = structlog.get_logger()
router = APIRouter()

# Tags/segmentos que disparam o agente automaticamente
ACTIVATION_KEYS = {
    "pos_fisio_neuro",
    "ativar_agente_pos_neuro",
    "ativar_agente",
    "lead_quente_pos_neuro",
}


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def _extract_nested(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def _extract_phone(payload: dict[str, Any]) -> str:
    lead_data = payload.get("lead") or {}
    raw = (
        _extract_nested(payload, "phone", "telefone", "whatsapp", "mobile")
        or _extract_nested(lead_data, "phone", "telefone", "whatsapp", "mobile")
        or ""
    )
    return _normalize_phone(str(raw))


def _extract_name(payload: dict[str, Any]) -> str | None:
    lead_data = payload.get("lead") or {}
    raw = (
        _extract_nested(payload, "name", "nome")
        or _extract_nested(lead_data, "name", "nome")
        or None
    )
    if not raw:
        return None
    return str(raw).strip()


def _extract_course(payload: dict[str, Any]) -> CourseSlug:
    lead_data = payload.get("lead") or {}
    raw = (
        _extract_nested(payload, "course_slug", "course", "curso")
        or _extract_nested(lead_data, "course_slug", "course", "curso")
        or ""
    )
    normalized = str(raw).strip().lower().replace(" ", "_")
    return CourseSlug.POS_FISIO_NEURO if normalized in {"pos_fisio_neuro", "pós_fisio_neuro", "pos_neuro"} else CourseSlug.UNKNOWN


def _extract_activation_tokens(payload: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()

    segment = payload.get("segment") or payload.get("segmento")
    if isinstance(segment, str) and segment.strip():
        tokens.add(segment.strip().lower().replace(" ", "_"))

    tags = payload.get("tags") or []
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str):
                norm = tag.strip().lower().replace(" ", "_")
                if norm:
                    tokens.add(norm)
            elif isinstance(tag, dict):
                name = (tag.get("name") or tag.get("nome") or "").strip().lower().replace(" ", "_")
                if name:
                    tokens.add(name)

    lead_data = payload.get("lead") or {}
    lead_tags = lead_data.get("tags") or []
    if isinstance(lead_tags, list):
        for tag in lead_tags:
            if isinstance(tag, str):
                norm = tag.strip().lower().replace(" ", "_")
                if norm:
                    tokens.add(norm)

    return tokens


def _authorize(webhook_key: str | None) -> None:
    if webhook_key != settings.app_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/sprinthub")
async def receive_sprinthub_webhook(
    request: Request,
    x_webhook_key: str | None = Header(default=None),
):
    """
    Recebe webhook do CRM para ativação outbound do agente.

    Fluxo:
    - Se lead entrar no segmento/tag de ativação da pós neuro, iniciamos script automaticamente.
    - Não depende do lead enviar mensagem primeiro no WhatsApp.
    """
    _authorize(x_webhook_key)
    payload = await request.json()

    phone = _extract_phone(payload)
    if not phone:
        return {"status": "ignored", "reason": "missing_phone"}

    course = _extract_course(payload)
    tokens = _extract_activation_tokens(payload)
    should_activate = course == CourseSlug.POS_FISIO_NEURO and bool(tokens.intersection(ACTIVATION_KEYS))

    if not should_activate:
        return {
            "status": "ignored",
            "reason": "activation_not_matched",
            "course": course.value,
            "tokens": sorted(tokens),
        }

    name = _extract_name(payload)
    lead = await get_or_create_lead(phone=phone, name=name)

    # Evita disparo duplicado se o script já iniciou para esse lead.
    if lead.course_slug == CourseSlug.POS_FISIO_NEURO and lead.stage == LeadStage.NURTURING and lead.script_step > 0:
        return {
            "status": "ignored",
            "reason": "already_running",
            "phone": phone,
            "script_step": lead.script_step,
        }

    lead = await update_lead_field(
        phone,
        name=name or lead.name,
        course_slug=CourseSlug.POS_FISIO_NEURO,
        stage=LeadStage.NURTURING,
        script_step=0,
        is_escalated=False,
        price_ask_count=0,
        followup_status="idle",
        followup_step=0,
        followup_next_at=None,
        followup_anchor_at=None,
        followup_started_at=None,
        followup_finished_at=None,
        followup_stopped_reason=None,
        price_sent_at=None,
    )

    asyncio.create_task(run_script_step(phone))

    logger.info(
        "✅ Agente ativado por webhook do CRM.",
        phone=phone,
        tokens=sorted(tokens),
        course=lead.course_slug.value,
    )

    return {
        "status": "started",
        "phone": phone,
        "course": lead.course_slug.value,
        "stage": lead.stage.value,
        "tokens": sorted(tokens),
    }
