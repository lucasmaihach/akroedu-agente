from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import httpx
import structlog
from tenacity import RetryError

from app.memory.session import (
    acquire_followup_lock,
    iter_leads,
    release_followup_lock,
    update_lead_field,
    get_lead,
    get_history,
)
from app.models.lead import Lead, CourseSlug, LeadStage
from app.followup.status import FollowupStatus
from app.services import whatsapp, escalation
from app.api.crm_webhooks import WELCOME_TEMPLATE_NAME
from app.utils.business_hours import now_utc, fit_business_hours, is_within_business_hours
from app.services.error_alert import notify_conversation_error
from app.services.telemetry import increment_metric
from app.utils.gender_detection import adapt_gender_text

logger = structlog.get_logger()

WINDOW_HOURS = 24
_FOLLOWUP_TERMINAL_STAGES = {LeadStage.CONVERTED, LeadStage.LOST, LeadStage.ESCALATED}

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
    "akro_posneuro_c1_d4",
]

C2_TEMPLATE_NAMES = [
    "akro_posneuro_c2_d1",
    "akro_posneuro_c2_d2",
    "akro_posneuro_c2_d3",
    "akro_posneuro_c2_d4",
    "akro_posneuro_c2_d5",
    "akro_posneuro_c2_d6",
]

_FOLLOWUP_CLOSING_HINTS = (
    "encerro por aqui por enquanto",
    "quando quiser retomar",
    "te atendo com prioridade",
)

_ENGAGEMENT_COLD_MIN_HOURS = 72
_ENGAGEMENT_WARM_MIN_HOURS = 36
_OUTBOUND_STREAK_HARD_STOP = 6


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


def _templates_enabled_for_lead(lead: Lead) -> bool:
    return lead.course_slug == CourseSlug.POS_FISIO_NEURO


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


def _is_template_step(lead: Lead, scenario: str, step: int) -> bool:
    if not _templates_enabled_for_lead(lead):
        return False
    return step >= 5


def _final_step_index(lead: Lead, scenario: str) -> int:
    if not _templates_enabled_for_lead(lead):
        return 4

    templates_len = len(C1_TEMPLATE_NAMES) if scenario == SCENARIO_PRE_PRICE else len(C2_TEMPLATE_NAMES)
    # 5 livres (0..4) + N templates (5..4+N)
    return 4 + templates_len


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


def _template_language_code(template_name: str) -> str:
    # Template cadastrado em produção com idioma "en".
    if template_name == "akro_posneuro_c2_d3":
        return "en"
    return "pt_BR"


def _followup_dedup_key(lead: Lead, scenario: str, step: int, channel: str) -> str:
    session_anchor = lead.followup_started_at.isoformat() if lead.followup_started_at else "na"
    return f"followup:{lead.phone_number}:{session_anchor}:{scenario}:step:{step}:{channel}"


def _is_followup_closing_message(text: str) -> bool:
    lower = (text or "").lower()
    return all(hint in lower for hint in _FOLLOWUP_CLOSING_HINTS)


async def _assistant_streak(lead: Lead, sample_size: int = 12) -> int:
    """
    Conta quantas mensagens do assistente aparecem em sequência no fim do histórico.
    Se o lead respondeu por último, retorna 0.
    """
    try:
        history = await get_history(lead.phone_number, last_n=sample_size)
    except Exception:
        return 0

    streak = 0
    for message in reversed(history):
        role = str(message.get("role", "")).strip().lower()
        if role == "assistant":
            streak += 1
            continue
        break
    return streak


def _engagement_gap_multiplier(idle_hours: float, assistant_streak: int) -> tuple[float, str]:
    """
    Ajusta o ritmo da régua para reduzir insistência em leads frios.
    """
    if idle_hours >= _ENGAGEMENT_COLD_MIN_HOURS or assistant_streak >= 4:
        return 2.4, "cold"
    if idle_hours >= _ENGAGEMENT_WARM_MIN_HOURS or assistant_streak >= 2:
        return 1.6, "warm"
    return 1.0, "hot"


async def stop_followup_on_inbound(lead: Lead, user_message: str) -> None:
    """Qualquer resposta do lead interrompe imediatamente a régua de follow-up."""
    now = now_utc()
    updates = {"last_inbound_at": now}

    if lead.followup_status == FollowupStatus.RUNNING:
        updates.update(
            {
                "followup_status": FollowupStatus.STOPPED.value,
                "followup_stopped_reason": "lead_replied",
                "followup_next_at": None,
                "followup_finished_at": now,
            }
        )

    updated = await update_lead_field(lead.phone_number, **updates)

    if lead.followup_status == FollowupStatus.RUNNING and (lead.followup_step or 0) > 0:
        await increment_metric("followup_stopped_total", tags={"reason": "lead_replied"})
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
    already_running = lead.followup_status == FollowupStatus.RUNNING and lead.followup_next_at is not None
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
        followup_status=FollowupStatus.RUNNING.value,
        followup_scenario=scenario,
        followup_step=0,
        followup_anchor_at=now,
        followup_started_at=now,
        followup_finished_at=None,
        followup_stopped_reason=None,
        followup_next_at=next_at,
    )
    await increment_metric("followup_scheduled_total", tags={"scenario": scenario, "source": source})

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
    if not lead.followup_enabled:
        return
    if lead.followup_status in (FollowupStatus.RUNNING, FollowupStatus.FINISHED):
        return

    scenario = _normalize_scenario(lead.followup_scenario, lead)
    current_step = lead.followup_step or 0
    final = _final_step_index(lead, scenario)

    if current_step > final:
        return  # sequência já concluída

    now = now_utc()
    # Aguarda 1h de cortesia antes de retomar a sequência
    next_at = fit_business_hours(now + timedelta(hours=1))

    await update_lead_field(
        lead.phone_number,
        followup_status=FollowupStatus.RUNNING.value,
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
    if not lead.followup_enabled:
        return

    token = await acquire_followup_lock(lead.phone_number, ttl_seconds=30)
    if not token:
        logger.info("🔒 Lock de follow-up ocupado; rearm será ignorado para evitar corrida.", phone=lead.phone_number)
        return

    try:
        fresh = await get_lead(lead.phone_number)
        if not fresh or not fresh.followup_enabled:
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
            lead.followup_enabled
            and lead.followup_status == FollowupStatus.RUNNING
            and lead.followup_next_at
            and lead.followup_next_at <= now
        )

        should_process_welcome = (
            lead.pending_welcome_template
            and lead.welcome_next_at
            and lead.welcome_next_at <= now
        )

        if lead.followup_status == FollowupStatus.RUNNING and not lead.followup_enabled:
            await update_lead_field(
                lead.phone_number,
                followup_status=FollowupStatus.STOPPED.value,
                followup_next_at=None,
                followup_stopped_reason="followup_disabled",
                notes="followup interrompido: flag followup_enabled=false",
            )
            await increment_metric("followup_stopped_total", tags={"reason": "followup_disabled"})
            continue

        if lead.followup_status == FollowupStatus.RUNNING and lead.followup_next_at is None:
            next_at = fit_business_hours(now + timedelta(minutes=15))
            await update_lead_field(
                lead.phone_number,
                followup_next_at=next_at,
                notes="followup reparado automaticamente: next_at ausente",
            )
            logger.warning(
                "Follow-up em running sem next_at; reagendado automaticamente.",
                phone=lead.phone_number,
                next_at=str(next_at),
            )
            await increment_metric("followup_repaired_total", tags={"reason": "missing_next_at"})
            continue

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

            fresh_should_process_followup = (
                fresh.followup_enabled
                and fresh.followup_status == FollowupStatus.RUNNING
                and fresh.followup_next_at
                and fresh.followup_next_at <= now
            )
            if fresh_should_process_followup:
                await _process_one(fresh)
        finally:
            await release_followup_lock(lead.phone_number, token)


async def _process_one(lead: Lead) -> None:
    now = now_utc()
    scenario = _normalize_scenario(lead.followup_scenario, lead)
    step = lead.followup_step

    if lead.stage in _FOLLOWUP_TERMINAL_STAGES:
        await update_lead_field(
            lead.phone_number,
            followup_status=FollowupStatus.STOPPED.value,
            followup_next_at=None,
            followup_finished_at=now,
            followup_stopped_reason=f"stage_{lead.stage.value}",
            notes=f"followup interrompido por estágio terminal ({lead.stage.value})",
        )
        await increment_metric("followup_stopped_total", tags={"reason": f"stage_{lead.stage.value}"})
        logger.info(
            "Follow-up interrompido por estágio terminal.",
            phone=lead.phone_number,
            stage=lead.stage.value,
        )
        return

    if scenario == SCENARIO_POST_PRICE and lead.price_sent_at is None:
        scenario = SCENARIO_PRE_PRICE
        await update_lead_field(lead.phone_number, followup_scenario=scenario)

    if not is_within_business_hours(now):
        next_at = fit_business_hours(now)
        await update_lead_field(lead.phone_number, followup_next_at=next_at)
        await increment_metric("conversation_event_total", tags={"category": "outside_hours_blocked", "component": "followup"})
        logger.info("🕒 Follow-up adiado por fora do horário comercial.", phone=lead.phone_number, next_at=str(next_at))
        return

    due_at = fit_business_hours(_step_due_at(lead, scenario, step))
    if now < due_at:
        await update_lead_field(lead.phone_number, followup_next_at=due_at)
        return

    assistant_streak = await _assistant_streak(lead)
    if assistant_streak >= _OUTBOUND_STREAK_HARD_STOP:
        await update_lead_field(
            lead.phone_number,
            followup_status=FollowupStatus.STOPPED.value,
            followup_next_at=None,
            followup_finished_at=now,
            followup_stopped_reason="outbound_streak_guard",
            notes=f"followup interrompido por sequência outbound sem resposta (streak={assistant_streak})",
        )
        await increment_metric("followup_stopped_total", tags={"reason": "outbound_streak_guard"})
        await increment_metric("conversation_event_total", tags={"category": "outbound_streak_blocked", "component": "followup"})
        logger.info(
            "🛑 Follow-up interrompido por excesso de outbound sem inbound.",
            phone=lead.phone_number,
            streak=assistant_streak,
            scenario=scenario,
            step=step,
        )
        return

    try:
        if _is_template_step(lead, scenario, step):
            template_name = _template_name(scenario, step)
            param = _first_name(lead) or "tudo bem"
            dedup_key = _followup_dedup_key(lead, scenario, step, f"template:{template_name}")
            await whatsapp.send_template(
                to=lead.phone_number,
                template_name=template_name,
                language_code=_template_language_code(template_name),
                body_params=[param],
                dedup_key=dedup_key,
            )
            await increment_metric("followup_sent_total", tags={"scenario": scenario, "channel": "template"})
        else:
            text = _free_text_for_step(lead, scenario, step)
            # Adapta gênero
            text = adapt_gender_text(text, lead.gender)
            dedup_key = _followup_dedup_key(lead, scenario, step, "text")
            await whatsapp.send_text(to=lead.phone_number, text=text, dedup_key=dedup_key)
            await increment_metric("followup_sent_total", tags={"scenario": scenario, "channel": "text"})

            # Se enviamos a mensagem explícita de encerramento, finaliza imediatamente
            # para não continuar rodando templates D+ depois do "encerro por aqui".
            if _is_followup_closing_message(text):
                await update_lead_field(
                    lead.phone_number,
                    followup_status=FollowupStatus.FINISHED.value,
                    followup_finished_at=now,
                    followup_next_at=None,
                    followup_stopped_reason="closing_message_sent",
                    notes="followup encerrado após mensagem final",
                )
                logger.info("✅ Régua de follow-up finalizada por mensagem de encerramento.", phone=lead.phone_number, scenario=scenario)
                await increment_metric("followup_finished_total", tags={"reason": "closing_message_sent"})
                return

        if step >= _final_step_index(lead, scenario):
            await update_lead_field(
                lead.phone_number,
                followup_status=FollowupStatus.FINISHED.value,
                followup_finished_at=now,
                followup_next_at=None,
                followup_stopped_reason="sequence_completed",
                notes="sequencia encerrada",
            )
            logger.info("✅ Régua de follow-up finalizada.", phone=lead.phone_number, scenario=scenario)
            await increment_metric("followup_finished_total", tags={"reason": "sequence_completed"})
            return

        next_step = step + 1

        # Preserva o intervalo original entre steps.
        # Se o servidor ficou offline e vários steps venceram, o próximo é agendado
        # com o mesmo gap relativo a partir de agora (ex: steps com gap de 6h e 4h
        # saem como +6h e +4h a partir do envio atual, não colados).
        original_gap = _step_due_at(lead, scenario, next_step) - _step_due_at(lead, scenario, step)
        reference = lead.last_inbound_at or lead.followup_anchor_at or now
        idle_hours = max(0.0, (now - reference).total_seconds() / 3600)
        multiplier, engagement_tier = _engagement_gap_multiplier(idle_hours, assistant_streak)
        adjusted_gap = min(original_gap * multiplier, timedelta(hours=48))
        next_at = fit_business_hours(now + adjusted_gap)
        await update_lead_field(
            lead.phone_number,
            followup_step=next_step,
            followup_next_at=next_at,
        )
        if multiplier > 1.0:
            await increment_metric(
                "followup_cadence_adjusted_total",
                tags={"scenario": scenario, "tier": engagement_tier},
            )

        logger.info(
            "📨 Follow-up enviado.",
            phone=lead.phone_number,
            scenario=scenario,
            step=step,
            next_step=next_step,
            next_at=str(next_at),
            cadence_tier=engagement_tier,
            cadence_multiplier=multiplier,
        )
    except Exception as e:
        cause = e
        if isinstance(e, RetryError):
            cause = e.last_attempt.exception() or e

        is_permanent_client_error = (
            isinstance(cause, httpx.HTTPStatusError)
            and cause.response is not None
            and 400 <= cause.response.status_code < 500
            and cause.response.status_code != 429
        )

        logger.error("Erro ao processar follow-up.", phone=lead.phone_number, scenario=scenario, step=step, error=str(e))

        if is_permanent_client_error:
            status = cause.response.status_code
            detail = (cause.response.text or "")[:220]
            await update_lead_field(
                lead.phone_number,
                followup_status=FollowupStatus.STOPPED.value,
                followup_next_at=None,
                followup_stopped_reason=f"delivery_error_http_{status}",
                notes=f"followup halted at step={step}: {detail}",
            )
            await increment_metric("followup_failed_total", tags={"reason": f"http_{status}"})
            await increment_metric("followup_stopped_total", tags={"reason": f"delivery_error_http_{status}"})
            logger.warning(
                "🛑 Follow-up interrompido por erro permanente de entrega.",
                phone=lead.phone_number,
                step=step,
                status=status,
            )
            return

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
