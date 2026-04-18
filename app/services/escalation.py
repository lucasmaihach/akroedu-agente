import structlog
from app.models.lead import Lead, LeadStage
from app.memory.session import save_lead, acquire_ops_alert_cooldown
from app.services import whatsapp, crm, ops_alert
from app.services.telemetry import increment_metric

logger = structlog.get_logger()

# Frases que indicam que o lead quer falar com humano
HUMAN_TRIGGERS = [
    "falar com humano",
    "falar com uma pessoa",
    "atendente",
    "quero um atendente",
    "pessoa real",
    "vendedor",
    "consultor",
    "não quero falar com robô",
    "não é robô",
    "é robô",
    "é um bot",
    "preciso de ajuda humana",
]


def should_escalate_by_message(text: str) -> bool:
    """Verifica se a mensagem do lead pede explicitamente por humano."""
    lower = text.lower()
    return any(trigger in lower for trigger in HUMAN_TRIGGERS)


async def notify_human_only(
    lead: Lead,
    reason: str,
    user_message: str = "",
    *,
    dedup_key: str | None = None,
    dedup_ttl_seconds: int = 30 * 60,
) -> bool:
    """
    Apenas notifica o canal interno de operações (Telegram), sem alterar estágio do lead.
    Útil para perguntas não mapeadas durante script ativo.
    """
    if dedup_key:
        can_notify = await acquire_ops_alert_cooldown(
            lead.phone_number,
            dedup_key,
            ttl_seconds=dedup_ttl_seconds,
        )
        if not can_notify:
            logger.info(
                "🔕 Alerta interno deduplicado por cooldown.",
                phone=lead.phone_number,
                dedup_key=dedup_key,
                reason=reason,
            )
            await increment_metric("conversation_event_total", tags={"category": "outside_faq_alert_deduped"})
            return False

    alert_message = (
        f"🟡 *Lead com pergunta para atendimento humano*\n\n"
        f"📱 *Número:* +{lead.phone_number}\n"
        f"👤 *Nome:* {lead.name or 'Não identificado'}\n"
        f"📚 *Curso:* {lead.course_slug.value}\n"
        f"📍 *Estágio:* {lead.stage.value}\n"
        f"📝 *Motivo:* {reason}\n"
        f"❓ *Pergunta:* {user_message or '(não informado)'}"
    )

    delivered = await ops_alert.send_internal_alert(alert_message)
    if not delivered:
        logger.warning(
            "Notificação interna não enviada (Telegram indisponível ou não configurado).",
            phone=lead.phone_number,
            reason=reason,
        )
        await increment_metric("conversation_error_total", tags={"category": "send_error", "channel": "telegram"})
        return False
    await increment_metric("conversation_event_total", tags={"category": "outside_faq_alert_sent"})
    return True


async def escalate(lead: Lead, reason: str = "Solicitado pelo lead") -> Lead:
    """
    Executa o fluxo de escalação:
    1. Atualiza o estágio do lead
    2. Notifica o lead via WhatsApp
    3. Sincroniza com o SprintHub
    4. Notifica operações no Telegram
    """
    if lead.is_escalated:
        logger.info("Lead já foi escalado anteriormente.", phone=lead.phone_number)
        return lead

    logger.info("🚨 Escalando lead para humano.", phone=lead.phone_number, reason=reason)

    # 1. Atualiza status
    lead = lead.model_copy(update={
        "stage": LeadStage.ESCALATED,
        "is_escalated": True,
        "notes": reason,
    })
    await save_lead(lead)

    # 2. Avisa o lead
    await whatsapp.send_text(
        to=lead.phone_number,
        text=(
            "Perfeito! 😊 Vou chamar um dos nossos consultores agora mesmo para te atender pessoalmente.\n\n"
            "Em breve ele entra em contato com você por aqui. Aguarde só um instante! 🙏"
        ),
    )

    # 3. Notifica operações no Telegram (canal interno).
    alert_message = (
        "🚨 Novo lead aguardando atendimento humano!\n\n"
        f"Número: +{lead.phone_number}\n"
        f"Nome: {lead.name or 'Não identificado'}\n"
        f"Curso de interesse: {lead.course_slug.value}\n"
        f"Estágio: {lead.stage.value}\n"
        f"Motivo: {reason}\n\n"
        "Por favor, entre em contato com o lead o quanto antes."
    )
    delivered = await ops_alert.send_internal_alert(alert_message)
    if not delivered:
        logger.warning(
            "Notificação interna não enviada durante escalate (Telegram indisponível).",
            phone=lead.phone_number,
            reason=reason,
        )

    # 4. Sincroniza com CRM
    await crm.sync_lead(lead)

    return lead
