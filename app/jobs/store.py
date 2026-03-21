from __future__ import annotations

import json
from datetime import timedelta

import structlog
from sqlalchemy import and_, select, update

from app.db.database import AsyncSessionLocal
from app.db.orm_models import PendingJobORM
from app.utils.business_hours import now_utc

logger = structlog.get_logger()


def _db_now():
    """Retorna datetime UTC naive para colunas TIMESTAMP WITHOUT TIME ZONE."""
    return now_utc().replace(tzinfo=None)


JOB_TYPE_DEBOUNCE_INBOUND = "debounce_inbound"
JOB_TYPE_FAQ_REPLY_RESUME = "faq_reply_resume"

_PENDING_STATUSES = ("pending", "running")


async def schedule_debounce_inbound(
    phone: str,
    contact_name: str | None,
    message_text: str,
    delay_seconds: int,
) -> None:
    """Acumula mensagens inbound em um job persistente de debounce."""
    inbound_at = _db_now()
    run_at = inbound_at + timedelta(seconds=delay_seconds)

    async with AsyncSessionLocal() as session:
        stmt = (
            select(PendingJobORM)
            .where(
                PendingJobORM.job_type == JOB_TYPE_DEBOUNCE_INBOUND,
                PendingJobORM.phone_number == phone,
                PendingJobORM.status == "pending",
            )
            .order_by(PendingJobORM.id.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        current = result.scalar_one_or_none()

        if current:
            payload = _safe_payload(current.payload)
            messages = payload.get("messages") or []
            if message_text and message_text.strip():
                messages.append(message_text.strip())
            payload["messages"] = messages
            payload["contact_name"] = contact_name
            payload["last_inbound_at"] = inbound_at.isoformat()

            current.payload = json.dumps(payload, ensure_ascii=False)
            current.run_at = run_at
            current.status = "pending"
            current.last_error = None
        else:
            payload = {
                "contact_name": contact_name,
                "messages": [message_text.strip()] if message_text and message_text.strip() else [],
                "last_inbound_at": inbound_at.isoformat(),
            }
            session.add(
                PendingJobORM(
                    job_type=JOB_TYPE_DEBOUNCE_INBOUND,
                    phone_number=phone,
                    run_at=run_at,
                    payload=json.dumps(payload, ensure_ascii=False),
                    status="pending",
                )
            )

        await session.commit()


async def schedule_faq_reply_resume(
    phone: str,
    faq_response: str,
    user_message: str,
    notify_human: bool,
    expected_script_step: int,
    delay_seconds: int,
) -> None:
    """Agenda resposta de FAQ + retomada de script de forma persistente."""
    scheduled_at = _db_now()
    run_at = scheduled_at + timedelta(seconds=delay_seconds)
    payload = {
        "faq_response": faq_response,
        "user_message": user_message,
        "notify_human": notify_human,
        "expected_script_step": expected_script_step,
        "scheduled_at": scheduled_at.isoformat(),
    }

    async with AsyncSessionLocal() as session:
        cancel_stmt = (
            update(PendingJobORM)
            .where(
                PendingJobORM.job_type == JOB_TYPE_FAQ_REPLY_RESUME,
                PendingJobORM.phone_number == phone,
                PendingJobORM.status.in_(_PENDING_STATUSES),
            )
            .values(status="cancelled", completed_at=_db_now())
        )
        await session.execute(cancel_stmt)

        session.add(
            PendingJobORM(
                job_type=JOB_TYPE_FAQ_REPLY_RESUME,
                phone_number=phone,
                run_at=run_at,
                payload=json.dumps(payload, ensure_ascii=False),
                status="pending",
            )
        )
        await session.commit()


async def claim_due_jobs(limit: int = 50) -> list[PendingJobORM]:
    """Faz claim otimista dos jobs vencidos para execução."""
    now = _db_now()
    claimed_ids: list[int] = []

    async with AsyncSessionLocal() as session:
        stmt = (
            select(PendingJobORM)
            .where(PendingJobORM.status == "pending", PendingJobORM.run_at <= now)
            .order_by(PendingJobORM.run_at.asc(), PendingJobORM.id.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        jobs = list(result.scalars().all())

        for job in jobs:
            upd = (
                update(PendingJobORM)
                .where(PendingJobORM.id == job.id, PendingJobORM.status == "pending")
                .values(status="running", started_at=now, attempts=job.attempts + 1)
            )
            update_result = await session.execute(upd)
            if update_result.rowcount:
                claimed_ids.append(job.id)

        await session.commit()

    if not claimed_ids:
        return []

    async with AsyncSessionLocal() as session:
        claimed_stmt = select(PendingJobORM).where(PendingJobORM.id.in_(claimed_ids)).order_by(PendingJobORM.id.asc())
        claimed_result = await session.execute(claimed_stmt)
        return list(claimed_result.scalars().all())


async def complete_job(job_id: int) -> None:
    async with AsyncSessionLocal() as session:
        stmt = (
            update(PendingJobORM)
            .where(PendingJobORM.id == job_id)
            .values(status="done", completed_at=_db_now(), last_error=None)
        )
        await session.execute(stmt)
        await session.commit()


async def reschedule_job(job_id: int, run_at, error: str | None = None) -> None:
    async with AsyncSessionLocal() as session:
        stmt = (
            update(PendingJobORM)
            .where(PendingJobORM.id == job_id)
            .values(status="pending", run_at=run_at, last_error=error)
        )
        await session.execute(stmt)
        await session.commit()


async def mark_job_failed(job_id: int, error: str) -> None:
    async with AsyncSessionLocal() as session:
        stmt = (
            update(PendingJobORM)
            .where(PendingJobORM.id == job_id)
            .values(status="failed", completed_at=_db_now(), last_error=error)
        )
        await session.execute(stmt)
        await session.commit()


async def reset_stale_running_jobs(max_running_minutes: int = 15) -> int:
    """Reativa jobs que ficaram em running após restart/crash."""
    threshold = _db_now() - timedelta(minutes=max_running_minutes)
    async with AsyncSessionLocal() as session:
        stmt = (
            update(PendingJobORM)
            .where(
                PendingJobORM.status == "running",
                and_(
                    PendingJobORM.started_at.is_not(None),
                    PendingJobORM.started_at <= threshold,
                ),
            )
            .values(status="pending", run_at=_db_now(), started_at=None)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount or 0


def _safe_payload(raw_payload: str | None) -> dict:
    if not raw_payload:
        return {}
    try:
        value = json.loads(raw_payload)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}
