import asyncio
import re
import unicodedata
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings
from app.memory.session import get_or_create_lead, update_lead_field
from app.models.lead import CourseSlug, LeadStage
from app.script.engine import SCRIPT_CONFIGS, run_script_step

logger = structlog.get_logger()
router = APIRouter()

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


def _normalize_text(value: str) -> str:
    clean = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    clean = clean.lower().strip()
    clean = re.sub(r"[^a-z0-9]+", "_", clean)
    return re.sub(r"_+", "_", clean).strip("_")


def _build_course_aliases() -> dict[CourseSlug, set[str]]:
    aliases: dict[CourseSlug, set[str]] = {
        CourseSlug.CURSO_1: {"curso_1", "curso1", "gestao_de_projetos", "lideranca"},
        CourseSlug.CURSO_2: {"curso_2", "curso2", "marketing_digital", "ecommerce", "e_commerce"},
        CourseSlug.POS_FISIO_NEURO: {
            "pos_fisio_neuro",
            "pos_neuro",
            "fisio_neuro",
            "fisioterapia_neurofuncional",
            "neurofuncional",
        },
    }

    for slug, config in SCRIPT_CONFIGS.items():
        name = config.get("name")
        if isinstance(name, str) and name.strip() and slug in aliases:
            aliases[slug].add(_normalize_text(name))

    return aliases


COURSE_ALIASES = _build_course_aliases()


def _extract_product_name(payload: dict[str, Any]) -> str | None:
    lead_data = payload.get("lead") or {}
    raw = (
        _extract_nested(payload, "product_name", "produto_nome", "product", "produto", "offer", "oferta", "pipeline_name", "pipeline")
        or _extract_nested(lead_data, "product_name", "produto_nome", "product", "produto", "offer", "oferta", "pipeline_name", "pipeline")
    )
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _course_from_token(token: str) -> CourseSlug:
    if not token:
        return CourseSlug.UNKNOWN

    normalized = _normalize_text(token)

    for slug, aliases in COURSE_ALIASES.items():
        if normalized in aliases:
            return slug

    if "neuro" in normalized and ("fisio" in normalized or "fisioterapia" in normalized):
        return CourseSlug.POS_FISIO_NEURO

    if ("gestao" in normalized and "projet" in normalized) or "lideranca" in normalized:
        return CourseSlug.CURSO_1

    if "marketing" in normalized and ("digital" in normalized or "ecommerce" in normalized):
        return CourseSlug.CURSO_2

    return CourseSlug.UNKNOWN


def _extract_course(payload: dict[str, Any], product_name: str | None) -> CourseSlug:
    lead_data = payload.get("lead") or {}
    raw_course = (
        _extract_nested(payload, "course_slug", "course", "curso")
        or _extract_nested(lead_data, "course_slug", "course", "curso")
    )

    candidates = [
        str(raw_course).strip() if raw_course is not None else "",
        product_name or "",
    ]

    for candidate in candidates:
        slug = _course_from_token(candidate)
        if slug != CourseSlug.UNKNOWN:
            return slug

    return CourseSlug.UNKNOWN


def _authorize(webhook_key: str | None) -> None:
    if webhook_key != settings.app_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/sprinthub")
async def receive_sprinthub_webhook(
    request: Request,
    x_webhook_key: str | None = Header(default=None),
):
    """
    Recebe webhook de novo lead vindo do CRM (SprintHub).

    Regra de ativação:
    - O CRM envia automaticamente a cada novo lead.
    - O agente é definido pelo nome do produto/curso recebido no payload.
    - Não depende de tags/segmentos.
    """
    _authorize(x_webhook_key)
    payload = await request.json()

    phone = _extract_phone(payload)
    if not phone:
        return {"status": "ignored", "reason": "missing_phone"}

    product_name = _extract_product_name(payload)
    course = _extract_course(payload, product_name)

    if course == CourseSlug.UNKNOWN:
        return {
            "status": "ignored",
            "reason": "activation_not_matched",
            "course": course.value,
            "product_name": product_name,
        }

    name = _extract_name(payload)
    lead = await get_or_create_lead(phone=phone, name=name)

    # Evita disparo duplicado se o script já iniciou para esse mesmo curso.
    if lead.course_slug == course and lead.stage == LeadStage.NURTURING and lead.script_step > 0:
        return {
            "status": "ignored",
            "reason": "already_running",
            "phone": phone,
            "script_step": lead.script_step,
        }

    lead = await update_lead_field(
        phone,
        name=name or lead.name,
        course_slug=course,
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
        product_name=product_name,
        course=lead.course_slug.value,
    )

    return {
        "status": "started",
        "phone": phone,
        "course": lead.course_slug.value,
        "stage": lead.stage.value,
        "product_name": product_name,
    }
