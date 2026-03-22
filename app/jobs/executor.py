from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import structlog

from app.agents.dispatcher import dispatch
from app.jobs.store import (
    JOB_TYPE_DEBOUNCE_INBOUND,
    JOB_TYPE_FAQ_REPLY_RESUME,
    claim_due_jobs,
    complete_job,
    mark_job_failed,
    reset_stale_running_jobs,
    reschedule_job,
)
from app.memory.session import get_lead, get_or_create_lead
from app.script.engine import run_script_step
from app.services import escalation, whatsapp
from app.utils.business_hours import fit_business_hours, is_within_business_hours, now_utc

logger = structlog.get_logger()

MAX_ATTEMPTS = 8
NON_SCRIPT_RESPONSE_DELAY_SECONDS = 2


def _as_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


async def resume_pending_jobs_on_startup() -> None:
    recovered = await reset_stale_running_jobs(max_running_minutes=10)
    if recovered:
        logger.info("♻️ Jobs pendentes recuperados após restart.", recovered=recovered)


async def process_due_pending_jobs() -> None:
    jobs = await claim_due_jobs(limit=50)
    if not jobs:
        return

    for job in jobs:
        try:
            payload = _load_payload(job.payload)

            if job.job_type == JOB_TYPE_DEBOUNCE_INBOUND:
                await _execute_debounce_inbound(job.id, job.phone_number, payload)
            elif job.job_type == JOB_TYPE_FAQ_REPLY_RESUME:
                await _execute_faq_reply_resume(job.id, job.phone_number, payload)
            else:
                logger.warning("Tipo de job desconhecido; marcando como concluído.", job_id=job.id, job_type=job.job_type)
                await complete_job(job.id)

        except Exception as e:
            logger.error("Erro ao executar pending job.", job_id=job.id, job_type=job.job_type, error=str(e))

            if job.attempts >= MAX_ATTEMPTS:
                await mark_job_failed(job.id, error=str(e))
                continue

            retry_at = fit_business_hours(now_utc() + timedelta(minutes=5))
            await reschedule_job(job.id, run_at=retry_at, error=str(e))
            await asyncio.sleep(0)


async def _execute_debounce_inbound(job_id: int, phone: str, payload: dict) -> None:
    now = now_utc()
    if not is_within_business_hours(now):
        await reschedule_job(job_id, run_at=fit_business_hours(now), error=None)
        return

    job_last_inbound_at = _parse_iso_datetime(payload.get("last_inbound_at"))
    current_lead = await get_lead(phone)
    lead_last_inbound_at = _as_naive_utc(current_lead.last_inbound_at) if current_lead else None
    if (
        current_lead
        and lead_last_inbound_at
        and job_last_inbound_at
        and lead_last_inbound_at > job_last_inbound_at
    ):
        logger.info(
            "⏭️ Job de debounce ignorado por existir inbound mais recente.",
            phone=phone,
            job_id=job_id,
            job_last_inbound_at=str(job_last_inbound_at),
            lead_last_inbound_at=str(lead_last_inbound_at),
        )
        await complete_job(job_id)
        return

    messages = payload.get("messages") or []
    contact_name = payload.get("contact_name")

    merged_text = "\n".join([m.strip() for m in messages if isinstance(m, str) and m.strip()]).strip()
    if not merged_text:
        await complete_job(job_id)
        return

    lead = await get_or_create_lead(phone=phone, name=contact_name)

    # Reage à última mensagem do lead com ❤️ (uma reação por janela de debounce)
    last_msg_id = lead.last_received_msg_id
    if last_msg_id:
        await whatsapp.send_reaction(to=phone, message_id=last_msg_id, emoji="❤️")

    should_advance_script, acolhimento_text = await dispatch(lead=lead, user_message=merged_text)
    if should_advance_script:
        job_script_step = payload.get("script_step")
        refreshed_lead = await get_lead(phone)
        if (
            job_script_step is not None
            and refreshed_lead is not None
            and refreshed_lead.script_step != job_script_step
        ):
            logger.info(
                "⏭️ Script já avançou desde o debounce — avanço ignorado para evitar salto duplo.",
                phone=phone,
                job_id=job_id,
                job_script_step=job_script_step,
                current_script_step=refreshed_lead.script_step,
            )
        else:
            await run_script_step(phone, acolhimento_override=acolhimento_text)

    logger.info(
        "⏱️ Inbound processado por job persistente.",
        phone=phone,
        messages_buffered=len(messages),
        advance_script=should_advance_script,
    )

    await complete_job(job_id)


async def _execute_faq_reply_resume(job_id: int, phone: str, payload: dict) -> None:
    now = now_utc()
    if not is_within_business_hours(now):
        await reschedule_job(job_id, run_at=fit_business_hours(now), error=None)
        return

    faq_response = payload.get("faq_response")
    user_message = payload.get("user_message", "")
    notify_human = bool(payload.get("notify_human"))
    expected_script_step = int(payload.get("expected_script_step", 0))

    if not faq_response:
        await complete_job(job_id)
        return

    lead = await get_lead(phone)
    if lead is None or lead.is_escalated:
        await complete_job(job_id)
        return

    scheduled_at = _parse_iso_datetime(payload.get("scheduled_at"))
    lead_last_inbound_at = _as_naive_utc(lead.last_inbound_at)
    if lead_last_inbound_at and scheduled_at and lead_last_inbound_at > scheduled_at:
        logger.info(
            "⏭️ Job de FAQ ignorado por existir inbound após agendamento.",
            phone=phone,
            job_id=job_id,
            scheduled_at=str(scheduled_at),
            lead_last_inbound_at=str(lead_last_inbound_at),
        )
        await complete_job(job_id)
        return

    if NON_SCRIPT_RESPONSE_DELAY_SECONDS > 0:
        await whatsapp.send_typing_and_wait(
            message_id=lead.last_received_msg_id or "",
            duration_seconds=NON_SCRIPT_RESPONSE_DELAY_SECONDS,
        )
    faq_dedup = f"faq_resume:{phone}:{expected_script_step}:{scheduled_at.isoformat() if scheduled_at else 'na'}"
    await whatsapp.send_text(to=lead.phone_number, text=faq_response, dedup_key=faq_dedup)

    if notify_human:
        await escalation.notify_human_only(
            lead=lead,
            reason="Pergunta sensível de FAQ (cancelamento/reembolso)",
            user_message=user_message,
        )

    refreshed_lead = await get_lead(phone)
    if refreshed_lead is None or refreshed_lead.is_escalated:
        await complete_job(job_id)
        return

    if refreshed_lead.script_step != expected_script_step:
        logger.info(
            "FAQ respondido, mas script já avançou por outro evento; retomada automática ignorada.",
            phone=phone,
            expected_step=expected_script_step,
            current_step=refreshed_lead.script_step,
        )
        await complete_job(job_id)
        return

    await run_script_step(phone, retry_on_lock=False)
    logger.info(
        "FAQ respondido por job persistente e script retomado automaticamente.",
        phone=phone,
        step=expected_script_step,
        notify_human=notify_human,
    )

    await complete_job(job_id)


def _load_payload(raw_payload: str | None) -> dict:
    if not raw_payload:
        return {}
    try:
        payload = json.loads(raw_payload)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _parse_iso_datetime(raw_value: str | None) -> datetime | None:
    if not raw_value:
        return None
    try:
        dt = datetime.fromisoformat(raw_value)
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None
