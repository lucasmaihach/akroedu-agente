from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

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
from app.api.crm_webhooks import WELCOME_TEMPLATE_NAME
from app.utils.business_hours import now_utc, fit_business_hours, is_within_business_hours
from app.services.error_alert import notify_conversation_error

logger = structlog.get_logger()

WINDOW_HOURS = 24

SCENARIO_PRE_PRICE = "pre_price"
SCENARIO_POST_PRICE = "post_price"


C1_FREE = [
    "Oi {name}, tudo bem? Quando puder, me chama por aqui e eu continuo te explicando a pós 😊",
    "Se fizer sentido pra você, eu te mando os próximos detalhes da formação. Posso continuar?",
    "Quero te ajudar a decidir com segurança, sem pressa. Você prefere que eu te explique primeiro conteúdo, rotina das aulas ou investimento?",
    "Oi {name}, fico à disposição. Se quiser, seguimos do ponto em que paramos e eu te explico tudo certinho 🙂",
    "Oi {name}, encerro por aqui por enquanto. Quando quiser retomar, é só me chamar que eu te atendo com prioridade 😊",
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


def _first_name(lead: Lead) -> str | None:
    if not lead.name:
        return None
    return lead.name.strip().split()[0]


def _window_end(lead: Lead) -> datetime:
    base = lead.last_inbound_at or lead.followup_anchor_at or now_utc()
    return base + timedelta(hours=WINDOW_HOURS)


def _scenario_for_lead(lead: Lead) -> str:
    return SCENARIO_POST_PRICE if lead.price_sent_at else SCENARIO_PRE_PRICE


def _normalize_scenario(raw_scenario: str | None, lead: Lead) -> str:
    if raw_scenario in {SCENARIO_PRE_PRICE, "C1"}:
        return SCENARIO_PRE_PRICE
    if raw_scenario in {SCENARIO_POST_PRICE, "C2"}:
        return SCENARIO_POST_PRICE
    return _scenario_for_lead(lead)


def _step_due_at(lead: Lead, scenario: str, step: int) -> datetime:
    anchor = lead.followup_anchor_at or now_utc()

    if scenario == SCENARIO_PRE_PRICE:
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
    return step >= 5


def _final_step_index(scenario: str) -> int:
    # Pré-preço: 5 livres + 4 templates = 9 passos (índice final 8)
    # Pós-preço: 5 livres + 8 templates = 13 passos (índice final 12)
    return 8 if scenario == SCENARIO_PRE_PRICE else 12


def _free_text_for_step(lead: Lead, scenario: str, step: int) -> str:
    name = _first_name(lead)
    if scenario == SCENARIO_PRE_PRICE:
        txt = C1_FREE[step]
    else:
        txt = C2_FREE[step]

    if name:
        return txt.format(name=name)

    return txt.replace("Oi {name}, ", "Oi, ").replace("{name}, ", "").replace("{name}", "")


def _template_name(scenario: str, step: int) -> str:
    return C1_TEMPLATE_NAMES[step - 5] if scenario == SCENARIO_PRE_PRICE else C2_TEMPLATE_NAMES[step - 5]


def _followup_dedup_key(lead: Lead, scenario: str, step: int, channel: str) -> str:
    session_anchor = lead.followup_started_at.isoformat() if lead.followup_started_at else "na"
    return f"followup:{lead.phone_number}:{session_anchor}:{scenario}:step:{step}:{channel}"


async def stop_followup_on_inbound(lead: Lead, user_message: str) -> None:
    """Qualquer resposta do lead interrompe imediatamente a régua de follow-up."""
    now = now_utc()
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

    if lead.followup_status == "running" and (lead.followup_step or 0) > 0:
        await escalation.notify_human_only(
            lead=updated,
            reason="Lead respondeu mensagem de follow-up",
            user_message=user_message,
        )
        logger.info("⛔ Follow-up interrompido por resposta do lead.", phone=lead.phone_number)


async def mark_price_sent(phone: str) -> None:
    await update_lead_field(phone, price_sent_at=now_utc())


async def _arm_followup_with_scenario(
    lead: Lead,
    scenario: str,
    *,
    force_restart: bool,
    source: str,
) -> None:
    now = now_utc()
    scenario = _normalize_scenario(scenario, lead)

    current_scenario = _normalize_scenario(lead.followup_scenario, lead)
    already_running = lead.followup_status == "running" and lead.followup_next_at is not None
    if already_running and not force_restart and current_scenario == scenario:
        logger.info(
            "↔️ Régua já ativa para o lead; rearm ignorado para evitar duplicidade.",
            phone=lead.phone_number,
            scenario=scenario,
            next_at=str(lead.followup_next_at),
            source=source,
        )
        return

    next_at = fit_business_hours(_step_due_at(lead.model_copy(update={"followup_anchor_at": now}), scenario, 0))

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

    logger.info(
        "🧭 Régua de follow-up armada.",
        phone=lead.phone_number,
        scenario=scenario,
        next_at=str(next_at),
        force_restart=force_restart,
        source=source,
    )


async def resume_followup_after_reply(lead: Lead) -> None:
    """
    Retoma a régua de follow-up após o lead responder a um template D+,
    quando o script já está encerrado e a régua foi interrompida ('stopped' ou 'idle').

    Diferente de arm_followup_waiting_reply, NÃO reinicia a sequência do zero —
    continua do passo atual (followup_step) com um intervalo fixo de 1h a partir
    do momento da resposta, evitando reenvio de mensagens já enviadas.
    """
    if lead.course_slug != CourseSlug.POS_FISIO_NEURO or not lead.followup_enabled:
        return
    if lead.followup_status in ("running", "finished"):
        return

    scenario = _normalize_scenario(lead.followup_scenario, lead)
    current_step = lead.followup_step or 0
    final = _final_step_index(scenario)

    if current_step > final:
        return  # sequência já concluída

    now = now_utc()
    # Aguarda 1h de cortesia antes de retomar a sequência
    next_at = fit_business_hours(now + timedelta(hours=1))

    await update_lead_field(
        lead.phone_number,
        followup_status="running",
        followup_next_at=next_at,
        followup_stopped_reason=None,
    )
    logger.info(
        "↩️ Follow-up retomado após resposta do lead ao template D+.",
        phone=lead.phone_number,
        scenario=scenario,
        step=current_step,
        next_at=str(next_at),
    )


async def arm_followup_waiting_reply(lead: Lead) -> None:
    """Ativa/reinicia a régua quando há outbound e aguardamos resposta do lead."""
    if lead.course_slug != CourseSlug.POS_FISIO_NEURO or not lead.followup_enabled:
        return

    token = await acquire_followup_lock(lead.phone_number, ttl_seconds=30)
    if not token:
        logger.info("🔒 Lock de follow-up ocupado; rearm será ignorado para evitar corrida.", phone=lead.phone_number)
        return

    try:
        fresh = await get_lead(lead.phone_number)
        if not fresh or fresh.course_slug != CourseSlug.POS_FISIO_NEURO or not fresh.followup_enabled:
            return

        scenario = _scenario_for_lead(fresh)
        await _arm_followup_with_scenario(
            fresh,
            scenario,
            force_restart=True,
            source="script_response_trigger",
        )
    finally:
        await release_followup_lock(lead.phone_number, token)


async def process_due_followups() -> None:
    now = now_utc()
    async for lead in iter_leads():
        should_process_followup = (
            lead.course_slug == CourseSlug.POS_FISIO_NEURO
            and lead.followup_enabled
            and lead.followup_status == "running"
            and lead.followup_next_at
            and lead.followup_next_at <= now
        )

        should_process_welcome = (
            lead.pending_welcome_template
            and lead.welcome_next_at
            and lead.welcome_next_at <= now
        )

        if not should_process_followup and not should_process_welcome:
            continue

        token = await acquire_followup_lock(lead.phone_number, ttl_seconds=60)
        if not token:
            continue

        try:
            fresh = await get_lead(lead.phone_number)
            if not fresh:
                continue

            if should_process_welcome:
                await _process_pending_welcome(fresh)
                fresh = await get_lead(lead.phone_number)
                if not fresh:
                    continue

            if should_process_followup:
                await _process_one(fresh)
        finally:
            await release_followup_lock(lead.phone_number, token)


async def _process_one(lead: Lead) -> None:
    now = now_utc()
    scenario = _normalize_scenario(lead.followup_scenario, lead)
    step = lead.followup_step

    if scenario == SCENARIO_POST_PRICE and lead.price_sent_at is None:
        scenario = SCENARIO_PRE_PRICE
        await update_lead_field(lead.phone_number, followup_scenario=scenario)

    if not is_within_business_hours(now):
        next_at = fit_business_hours(now)
        await update_lead_field(lead.phone_number, followup_next_at=next_at)
        logger.info("🕒 Follow-up adiado por fora do horário comercial.", phone=lead.phone_number, next_at=str(next_at))
        return

    due_at = fit_business_hours(_step_due_at(lead, scenario, step))
    if now < due_at:
        await update_lead_field(lead.phone_number, followup_next_at=due_at)
        return

    try:
        if _is_template_step(scenario, step):
            template_name = _template_name(scenario, step)
            param = _first_name(lead) or "tudo bem"
            dedup_key = _followup_dedup_key(lead, scenario, step, f"template:{template_name}")
            await whatsapp.send_template(
                to=lead.phone_number,
                template_name=template_name,
                language_code="pt_BR",
                body_params=[param],
                dedup_key=dedup_key,
            )
        else:
            text = _free_text_for_step(lead, scenario, step)
            dedup_key = _followup_dedup_key(lead, scenario, step, "text")
            await whatsapp.send_text(to=lead.phone_number, text=text, dedup_key=dedup_key)

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

        # Preserva o intervalo original entre steps.
        # Se o servidor ficou offline e vários steps venceram, o próximo é agendado
        # com o mesmo gap relativo a partir de agora (ex: steps com gap de 6h e 4h
        # saem como +6h e +4h a partir do envio atual, não colados).
        original_gap = _step_due_at(lead, scenario, next_step) - _step_due_at(lead, scenario, step)
        next_at = fit_business_hours(now + original_gap)
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
        await notify_conversation_error(
            source="followup.process_one",
            error=e,
            phone=lead.phone_number,
            lead_name=lead.name,
            stage=lead.stage.value,
            user_message="[followup send]",
            extra={"scenario": scenario, "step": step},
        )
        retry_at = fit_business_hours(now + timedelta(minutes=15))
        await update_lead_field(lead.phone_number, followup_next_at=retry_at)
        await asyncio.sleep(0)


async def _process_pending_welcome(lead: Lead) -> None:
    if not lead.pending_welcome_template:
        return

    now = now_utc()
    if not is_within_business_hours(now):
        next_at = fit_business_hours(now)
        await update_lead_field(lead.phone_number, welcome_next_at=next_at)
        logger.info("🕒 Template inicial pendente adiado por fora do horário comercial.", phone=lead.phone_number, next_at=str(next_at))
        return

    next_at = lead.welcome_next_at or fit_business_hours(now)
    if next_at > now:
        return

    try:
        template_name = lead.welcome_template_name or WELCOME_TEMPLATE_NAME
        dedup_key = f"welcome_pending:{lead.phone_number}:{template_name}:{int(next_at.timestamp())}"
        await whatsapp.send_template(
            to=lead.phone_number,
            template_name=template_name,
            language_code="pt_BR",
            dedup_key=dedup_key,
        )
        await update_lead_field(
            lead.phone_number,
            pending_welcome_template=False,
            welcome_template_name=None,
            welcome_next_at=None,
            awaiting_template_reply=True,
        )
        refreshed = await get_lead(lead.phone_number)
        if refreshed and refreshed.followup_enabled and refreshed.course_slug == CourseSlug.POS_FISIO_NEURO:
            await _arm_followup_with_scenario(
                refreshed,
                SCENARIO_PRE_PRICE,
                force_restart=False,
                source="pending_welcome_sent",
            )

        logger.info("✅ Template inicial pendente enviado no horário comercial.", phone=lead.phone_number)
    except Exception as e:
        retry_at = fit_business_hours(now_utc() + timedelta(minutes=30))
        await update_lead_field(lead.phone_number, welcome_next_at=retry_at)
        logger.error(
            "Erro ao enviar template inicial pendente.",
            phone=lead.phone_number,
            error=str(e),
            retry_at=str(retry_at),
        )
        await notify_conversation_error(
            source="followup.pending_welcome",
            error=e,
            phone=lead.phone_number,
            lead_name=lead.name,
            stage=lead.stage.value,
            user_message="[welcome template pending]",
            extra={"retry_at": str(retry_at)},
        )
