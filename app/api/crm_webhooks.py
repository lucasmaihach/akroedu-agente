import json
import re
import unicodedata
from datetime import timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings
from app.memory.session import get_or_create_lead, update_lead_field
from app.models.lead import CourseSlug, LeadStage
from app.services import whatsapp
from app.utils.business_hours import now_utc, fit_business_hours, is_within_business_hours

logger = structlog.get_logger()
router = APIRouter()

WELCOME_TEMPLATE_NAME = "boas_vindas_fisio"
PRE_PRICE_SCENARIO = "pre_price"
PRE_PRICE_FIRST_FOLLOWUP_HOURS = 2


def _unwrap_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Alguns CRMs encaminham o conteúdo útil dentro de "data"/"payload"/"body".
    Mantém compatibilidade com ambos formatos: plano e aninhado.
    """
    for key in ("data", "payload", "body"):
        nested = payload.get(key)
        if isinstance(nested, dict) and nested:
            return nested
    return payload

def _normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())

    # Canonicaliza Brasil para evitar duplicidade 11XXXXXXXXX vs 55XXXXXXXXXXX
    if digits.startswith("55") and len(digits) in (12, 13):
        return digits
    if len(digits) in (10, 11):
        return f"55{digits}"

    return digits


def _extract_nested(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def _extract_phone(payload: dict[str, Any]) -> str:
    lead_data = payload.get("lead") or {}
    raw = (
        _extract_nested(payload, "phone", "telefone", "whatsapp", "mobile", "celular")
        or _extract_nested(lead_data, "phone", "telefone", "whatsapp", "mobile", "celular")
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
            "pos_fineu",
            "pos_fisioneuro",
            "pos_fisio_neurofuncional",
        },
    }

    return aliases


COURSE_ALIASES = _build_course_aliases()


def _extract_product_name(payload: dict[str, Any]) -> str | None:
    lead_data = payload.get("lead") or {}
    opportunity_data = payload.get("oportunidade") or payload.get("opportunity") or {}
    custom_fields_data = payload.get("campos_customizados") or payload.get("custom_fields") or {}
    raw = (
        _extract_nested(payload, "product_name", "produto_nome", "product", "produto", "offer", "oferta", "pipeline_name", "pipeline", "informacao05")
        or _extract_nested(lead_data, "product_name", "produto_nome", "product", "produto", "offer", "oferta", "pipeline_name", "pipeline", "informacao05")
        or _extract_nested(opportunity_data, "product_name", "produto_nome", "product", "produto", "offer", "oferta", "pipeline_name", "pipeline", "titulo", "title")
        or _extract_nested(custom_fields_data, "product_name", "produto_nome", "product", "produto", "offer", "oferta", "informacao05")
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

    # Variações curtas usadas em CRMs (ex.: "pos_fineu")
    if "fineu" in normalized or "fisioneuro" in normalized:
        return CourseSlug.POS_FISIO_NEURO

    if ("gestao" in normalized and "projet" in normalized) or "lideranca" in normalized:
        return CourseSlug.CURSO_1

    if "marketing" in normalized and ("digital" in normalized or "ecommerce" in normalized):
        return CourseSlug.CURSO_2

    return CourseSlug.UNKNOWN


def _extract_course(payload: dict[str, Any], product_name: str | None) -> CourseSlug:
    lead_data = payload.get("lead") or {}
    opportunity_data = payload.get("oportunidade") or payload.get("opportunity") or {}
    raw_course = (
        _extract_nested(payload, "course_slug", "course", "curso")
        or _extract_nested(lead_data, "course_slug", "course", "curso")
        or _extract_nested(opportunity_data, "course_slug", "course", "curso")
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


def _extract_sprinthub_ids(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    lead_data = payload.get("lead") or {}
    opportunity_data = payload.get("oportunidade") or payload.get("opportunity") or {}

    lead_id = _extract_nested(payload, "lead_id", "contato_id") or _extract_nested(lead_data, "id", "lead_id", "contato_id")
    opportunity_id = _extract_nested(payload, "opportunity_id", "oportunidade_id") or _extract_nested(opportunity_data, "id", "opportunity_id", "oportunidade_id")

    lead_id_text = str(lead_id).strip() if lead_id not in (None, "") else None
    opportunity_id_text = str(opportunity_id).strip() if opportunity_id not in (None, "") else None
    return lead_id_text, opportunity_id_text


def _extract_crm_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    lead_data = payload.get("lead") or {}
    opportunity_data = payload.get("oportunidade") or payload.get("opportunity") or {}
    custom_fields_data = payload.get("campos_customizados") or payload.get("custom_fields") or {}
    meta_data = payload.get("meta") or {}

    return {
        "lead": {
            "id": _extract_nested(lead_data, "id", "lead_id"),
            "nome": _extract_nested(lead_data, "nome", "name"),
            "email": _extract_nested(lead_data, "email"),
            "whatsapp": _extract_nested(lead_data, "whatsapp", "phone", "telefone", "mobile", "celular"),
            "telefone": _extract_nested(lead_data, "telefone", "mobile", "celular", "phone"),
            "cidade": _extract_nested(lead_data, "cidade", "city"),
            "estado": _extract_nested(lead_data, "estado", "state"),
            "empresa": _extract_nested(lead_data, "empresa", "company"),
        },
        "oportunidade": {
            "id": _extract_nested(opportunity_data, "id", "opportunity_id", "oportunidade_id"),
            "titulo": _extract_nested(opportunity_data, "titulo", "title"),
            "valor": _extract_nested(opportunity_data, "valor", "value", "opportunity_value"),
            "status": _extract_nested(opportunity_data, "status", "opportunity_status"),
            "crm_id": _extract_nested(opportunity_data, "crm_id", "crm_column", "estagio_crm_column_id", "stage_id"),
            "estagio": _extract_nested(opportunity_data, "estagio", "stage", "stage_name"),
            "responsavel": _extract_nested(opportunity_data, "responsavel", "responsavel_id", "owner", "owner_id", "opportunity_user"),
            "data_criacao": _extract_nested(opportunity_data, "data_criacao", "created_at", "opportunity_createDate"),
        },
        "campos_customizados": {
            "produto": _extract_nested(custom_fields_data, "produto", "product", "product_name", "informacao05"),
            "formacao": _extract_nested(custom_fields_data, "formacao", "education"),
        },
        "meta": {
            "timestamp": _extract_nested(meta_data, "timestamp"),
        },
    }


def _merge_notes_with_crm(existing_notes: str | None, crm_snapshot: dict[str, Any]) -> str:
    data: dict[str, Any] = {}
    if existing_notes:
        try:
            parsed = json.loads(existing_notes)
            if isinstance(parsed, dict):
                data = parsed
            else:
                data = {"legacy_notes": str(existing_notes)}
        except Exception:
            data = {"legacy_notes": str(existing_notes)}

    data["sprinthub"] = crm_snapshot
    return json.dumps(data, ensure_ascii=False)


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
    raw_payload = await request.json()
    payload = _unwrap_payload(raw_payload)

    logger.info(
        "📥 Webhook SprintHub recebido.",
        top_level_keys=list(raw_payload.keys()) if isinstance(raw_payload, dict) else [],
        payload_keys=list(payload.keys()) if isinstance(payload, dict) else [],
    )

    phone = _extract_phone(payload)
    if not phone:
        logger.warning(
            "⚠️ SprintHub ignorado: telefone ausente.",
            payload_preview=str(payload)[:800],
        )
        return {"status": "ignored", "reason": "missing_phone"}

    product_name = _extract_product_name(payload)
    course = _extract_course(payload, product_name)

    if course == CourseSlug.UNKNOWN:
        logger.warning(
            "⚠️ SprintHub ignorado: curso não mapeado.",
            phone=phone,
            product_name=product_name,
            payload_preview=str(payload)[:800],
        )
        return {
            "status": "ignored",
            "reason": "activation_not_matched",
            "course": course.value,
            "product_name": product_name,
        }

    name = _extract_name(payload)
    sprinthub_lead_id, sprinthub_opportunity_id = _extract_sprinthub_ids(payload)
    crm_snapshot = _extract_crm_snapshot(payload)

    lead = await get_or_create_lead(phone=phone, name=name)

    # Idempotência forte para evitar reset do fluxo quando o CRM reenviar
    # o mesmo lead (ou atualizações do mesmo lead) em sequência.
    if lead.course_slug == course and lead.stage == LeadStage.NURTURING:
        if lead.awaiting_template_reply:
            logger.info(
                "ℹ️ SprintHub ignorado: já aguardando resposta do lead.",
                phone=phone,
                course=course.value,
            )
            return {
                "status": "ignored",
                "reason": "waiting_user_reply",
                "phone": phone,
                "course": course.value,
            }

        if lead.pending_welcome_template:
            logger.info(
                "ℹ️ SprintHub ignorado: template inicial já está agendado para horário comercial.",
                phone=phone,
                course=course.value,
                welcome_next_at=str(lead.welcome_next_at),
            )
            return {
                "status": "ignored",
                "reason": "welcome_already_scheduled",
                "phone": phone,
                "course": course.value,
                "welcome_next_at": str(lead.welcome_next_at) if lead.welcome_next_at else None,
            }

        logger.info(
            "ℹ️ SprintHub ignorado: fluxo já em execução.",
            phone=phone,
            course=course.value,
            script_step=lead.script_step,
        )
        return {
            "status": "ignored",
            "reason": "already_running",
            "phone": phone,
            "script_step": lead.script_step,
            "awaiting_template_reply": lead.awaiting_template_reply,
        }

    common_updates = dict(
        name=name or lead.name,
        course_slug=course,
        sprinthub_id=sprinthub_lead_id or lead.sprinthub_id,
        notes=_merge_notes_with_crm(lead.notes, crm_snapshot),
        stage=LeadStage.NURTURING,
        script_step=0,
        is_escalated=False,
        price_ask_count=0,
        price_sent_at=None,
    )

    followup_reset_updates = {
        "followup_status": "idle",
        "followup_scenario": None,
        "followup_step": 0,
        "followup_next_at": None,
        "followup_anchor_at": None,
        "followup_started_at": None,
        "followup_finished_at": None,
        "followup_stopped_reason": None,
    }

    if not is_within_business_hours(now_utc()):
        welcome_next_at = fit_business_hours(now_utc())
        lead = await update_lead_field(
            phone,
            awaiting_template_reply=False,
            pending_welcome_template=True,
            welcome_template_name=WELCOME_TEMPLATE_NAME,
            welcome_next_at=welcome_next_at,
            **common_updates,
            **followup_reset_updates,
        )
        logger.info(
            "🕒 Lead recebido fora do horário; template inicial agendado.",
            phone=phone,
            template=WELCOME_TEMPLATE_NAME,
            welcome_next_at=str(welcome_next_at),
            course=lead.course_slug.value,
        )
        return {
            "status": "scheduled",
            "reason": "outside_business_hours",
            "phone": phone,
            "course": lead.course_slug.value,
            "stage": lead.stage.value,
            "template": WELCOME_TEMPLATE_NAME,
            "welcome_next_at": str(welcome_next_at),
            "product_name": product_name,
            "sprinthub_lead_id": sprinthub_lead_id,
            "sprinthub_opportunity_id": sprinthub_opportunity_id,
            "crm_snapshot": crm_snapshot,
        }

    outbound_ref = sprinthub_opportunity_id or sprinthub_lead_id or phone
    welcome_dedup_key = f"crm_welcome:{phone}:{course.value}:{outbound_ref}:{WELCOME_TEMPLATE_NAME}"

    try:
        await whatsapp.send_template(
            to=phone,
            template_name=WELCOME_TEMPLATE_NAME,
            language_code="pt_BR",
            dedup_key=welcome_dedup_key,
        )
    except Exception as e:
        logger.error(
            "❌ Falha ao enviar template inicial do CRM.",
            phone=phone,
            template=WELCOME_TEMPLATE_NAME,
            error=str(e),
        )
        return {
            "status": "error",
            "reason": "template_send_failed",
            "phone": phone,
            "template": WELCOME_TEMPLATE_NAME,
        }

    followup_updates = {}
    if course == CourseSlug.POS_FISIO_NEURO:
        activation_now = now_utc()
        first_followup_at = fit_business_hours(activation_now + timedelta(hours=PRE_PRICE_FIRST_FOLLOWUP_HOURS))
        followup_updates = {
            "followup_status": "running",
            "followup_scenario": PRE_PRICE_SCENARIO,
            "followup_step": 0,
            "followup_anchor_at": activation_now,
            "followup_started_at": activation_now,
            "followup_finished_at": None,
            "followup_stopped_reason": None,
            "followup_next_at": first_followup_at,
        }

    lead = await update_lead_field(
        phone,
        awaiting_template_reply=True,
        pending_welcome_template=False,
        welcome_template_name=None,
        welcome_next_at=None,
        **common_updates,
        **followup_reset_updates,
        **followup_updates,
    )

    logger.info(
        "✅ Template inicial enviado por webhook do CRM; aguardando resposta do lead.",
        phone=phone,
        template=WELCOME_TEMPLATE_NAME,
        product_name=product_name,
        course=lead.course_slug.value,
        sprinthub_lead_id=sprinthub_lead_id,
        sprinthub_opportunity_id=sprinthub_opportunity_id,
        crm_snapshot=crm_snapshot,
    )

    return {
        "status": "template_sent_waiting_reply",
        "phone": phone,
        "course": lead.course_slug.value,
        "stage": lead.stage.value,
        "template": WELCOME_TEMPLATE_NAME,
        "product_name": product_name,
        "sprinthub_lead_id": sprinthub_lead_id,
        "sprinthub_opportunity_id": sprinthub_opportunity_id,
        "crm_snapshot": crm_snapshot,
    }
