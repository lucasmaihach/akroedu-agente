from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import structlog

from app.memory.session import (
    acquire_followup_lock,
    iter_leads,
    release_followup_lock,
    update_lead_field,
    get_lead,
)
from app.models.lead import Lead, CourseSlug
from app.services import whatsapp, escalation

logger = structlog.get_logger()

BRT = ZoneInfo("America/Sao_Paulo")
START_HOUR = 7
END_HOUR = 22
WINDOW_HOURS = 24


C1_FREE = [
    "Oi {name}, tá por aí? 😅",
    "Conseguiu ouvir o que te mandei?",
    "Nossa, você me deixou falando sozinha 😂\nMe fala uma coisa: você já atende pacientes neurológicos no seu consultório?",
    "Oi {name}, conseguiu ver minhas mensagens?",
    "Oi {name}, última mensagem por hoje.\nFica à vontade pra me chamar quando quiser retomar, tá? Tenho uma condição especial reservada pra você 🙂",
]

C2_FREE = [
    "Oi {name}, ficou alguma dúvida sobre o investimento? 😊",
    "{name}, o que travou? Financeiro, timing, dúvida sobre o conteúdo?\nMe fala que eu te ajudo a resolver 🙂",
    "{name}, você sumiu depois que falei do valor 😅\nNormal, é uma decisão importante. Mas me conta: o que tá te impedindo de avançar?",
    "Oi {name}! Uma coisa que não te falei ainda:\nA pós inclui tutorias de *marketing digital* — você aprende a captar pacientes e se posicionar online. Muita gente recupera o investimento só com isso.\nVale a conversa, né? 😉",
    "Oi {name}, passando aqui antes de encerrar o dia.\nA condição especial que te mostrei ainda tá válida. Amanhã não garanto o mesmo valor.\nMe chama se quiser garantir 👇",
]

C1_TEMPLATE_NAMES = [
    "akro_posneuro_c1_d1",
    "akro_posneuro_c1_d2",
    "akro_posneuro_c1_d3",
    "akro_posneuro_c1_d4",
]

C2_TEMPLATE_NAMES = [
    "akro_posneuro_c2_d1",
    "akro_posneuro_c2_d2",
    "akro_posneuro_c2_d3",
    "akro_posneuro_c2_d4",
    "akro_posneuro_c2_d5",
    "akro_posneuro_c2_d6",
    "akro_posneuro_c2_d7",
    "akro_posneuro_c2_d8",
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _first_name(lead: Lead) -> str | None:
    if not lead.name:
        return None
    return lead.name.strip().split()[0]


def _fit_business_hours(dt_utc: datetime) -> datetime:
    dt_brt = dt_utc.astimezone(BRT)
    if dt_brt.hour < START_HOUR:
        dt_brt = dt_brt.replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
    elif dt_brt.hour >= END_HOUR:
        next_day = dt_brt + timedelta(days=1)
        dt_brt = next_day.replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
    return dt_brt.astimezone(timezone.utc)


def _window_end(lead: Lead) -> datetime:
    base = lead.last_inbound_at or lead.followup_anchor_at or _now_utc()
    return base + timedelta(hours=WINDOW_HOURS)


def _scenario_for_lead(lead: Lead) -> str:
    return "C2" if lead.price_sent_at else "C1"


def _step_due_at(lead: Lead, scenario: str, step: int) -> datetime:
    anchor = lead.followup_anchor_at or _now_utc()

    if scenario == "C1":
        # F1..F5 em: 2h, 3h, 6h, 12h, 20h
        if step <= 4:
            return anchor + timedelta(hours=[2, 3, 6, 12, 20][step])

        # Templates encadeados:
        # D+1 no step 5; depois sempre 22h após o template anterior.
        if step == 5:
            return _window_end(lead) + timedelta(days=1)
        return _step_due_at(lead, scenario, step - 1) + timedelta(hours=22)

    # C2
    # F1..F5 em: 1h, 3h, 6h, 12h, 20h
    if step <= 4:
        return anchor + timedelta(hours=[1, 3, 6, 12, 20][step])

    # Templates encadeados:
    # D+1 no step 5; depois sempre 22h após o template anterior.
    if step == 5:
        return _window_end(lead) + timedelta(days=1)
    return _step_due_at(lead, scenario, step - 1) + timedelta(hours=22)


def _is_template_step(scenario: str, step: int) -> bool:
    return (scenario == "C1" and step >= 5) or (scenario == "C2" and step >= 5)


def _final_step_index(scenario: str) -> int:
    # C1: 5 livres + 4 templates = 9 passos (índice final 8)
    # C2: 5 livres + 8 templates = 13 passos (índice final 12)
    return 8 if scenario == "C1" else 12


def _free_text_for_step(lead: Lead, scenario: str, step: int) -> str:
    name = _first_name(lead)
    if scenario == "C1":
        txt = C1_FREE[step]
    else:
        txt = C2_FREE[step]

    if name:
        return txt.format(name=name)

    return txt.replace("Oi {name}, ", "Oi, ").replace("{name}, ", "").replace("{name}", "")


def _template_name(scenario: str, step: int) -> str:
    return C1_TEMPLATE_NAMES[step - 5] if scenario == "C1" else C2_TEMPLATE_NAMES[step - 5]


async def stop_followup_on_inbound(lead: Lead, user_message: str) -> None:
    """Qualquer resposta do lead interrompe imediatamente a régua de follow-up."""
    now = _now_utc()
    updates = {"last_inbound_at": now}

    if lead.followup_status == "running":
        updates.update(
            {
                "followup_status": "stopped",
                "followup_stopped_reason": "lead_replied",
                "followup_next_at": None,
                "followup_finished_at": now,
            }
        )

    updated = await update_lead_field(lead.phone_number, **updates)

    if lead.followup_status == "running":
        await escalation.notify_human_only(
            lead=updated,
            reason="Lead respondeu mensagem de follow-up",
            user_message=user_message,
        )
        logger.info("⛔ Follow-up interrompido por resposta do lead.", phone=lead.phone_number)


async def mark_price_sent(phone: str) -> None:
    await update_lead_field(phone, price_sent_at=_now_utc())


async def arm_followup_waiting_reply(lead: Lead) -> None:
    """Ativa/reinicia a régua quando há outbound e aguardamos resposta do lead."""
    if lead.course_slug != CourseSlug.POS_FISIO_NEURO or not lead.followup_enabled:
        return

    scenario = _scenario_for_lead(lead)
    now = _now_utc()
    next_at = _fit_business_hours(_step_due_at(lead.model_copy(update={"followup_anchor_at": now}), scenario, 0))

    await update_lead_field(
        lead.phone_number,
        followup_status="running",
        followup_scenario=scenario,
        followup_step=0,
        followup_anchor_at=now,
        followup_started_at=now,
        followup_finished_at=None,
        followup_stopped_reason=None,
        followup_next_at=next_at,
    )

    logger.info("🧭 Régua de follow-up armada.", phone=lead.phone_number, scenario=scenario, next_at=str(next_at))


async def process_due_followups() -> None:
    now = _now_utc()
    async for lead in iter_leads():
        if lead.course_slug != CourseSlug.POS_FISIO_NEURO:
            continue
        if not lead.followup_enabled or lead.followup_status != "running" or not lead.followup_next_at:
            continue
        if lead.followup_next_at > now:
            continue

        token = await acquire_followup_lock(lead.phone_number, ttl_seconds=60)
        if not token:
            continue

        try:
            fresh = await get_lead(lead.phone_number)
            if not fresh:
                continue
            await _process_one(fresh)
        finally:
            await release_followup_lock(lead.phone_number, token)


async def _process_one(lead: Lead) -> None:
    now = _now_utc()
    scenario = lead.followup_scenario or _scenario_for_lead(lead)
    step = lead.followup_step

    due_at = _fit_business_hours(_step_due_at(lead, scenario, step))
    if now < due_at:
        await update_lead_field(lead.phone_number, followup_next_at=due_at)
        return

    try:
        if _is_template_step(scenario, step):
            template_name = _template_name(scenario, step)
            param = _first_name(lead) or "tudo bem"
            await whatsapp.send_template(
                to=lead.phone_number,
                template_name=template_name,
                language_code="pt_BR",
                body_params=[param],
            )
        else:
            text = _free_text_for_step(lead, scenario, step)
            await whatsapp.send_text(to=lead.phone_number, text=text)

        if step >= _final_step_index(scenario):
            await update_lead_field(
                lead.phone_number,
                followup_status="finished",
                followup_finished_at=now,
                followup_next_at=None,
                followup_stopped_reason="sequence_completed",
                notes="sequencia encerrada",
            )
            logger.info("✅ Régua de follow-up finalizada.", phone=lead.phone_number, scenario=scenario)
            return

        next_step = step + 1
        next_at = _fit_business_hours(_step_due_at(lead, scenario, next_step))
        await update_lead_field(
            lead.phone_number,
            followup_step=next_step,
            followup_next_at=next_at,
        )

        logger.info(
            "📨 Follow-up enviado.",
            phone=lead.phone_number,
            scenario=scenario,
            step=step,
            next_step=next_step,
            next_at=str(next_at),
        )
    except Exception as e:
        logger.error("Erro ao processar follow-up.", phone=lead.phone_number, scenario=scenario, step=step, error=str(e))
        retry_at = _fit_business_hours(now + timedelta(minutes=15))
        await update_lead_field(lead.phone_number, followup_next_at=retry_at)
        await asyncio.sleep(0)
