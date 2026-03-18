import structlog
from app.config import settings
from app.models.lead import Lead, LeadStage
from app.memory.session import update_lead_field, save_lead
from app.services import whatsapp, crm

logger = structlog.get_logger()


def _normalize_phone(phone: str) -> str:
    """Mantém somente dígitos para envio na API da Meta."""
    return "".join(ch for ch in phone if ch.isdigit())

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


async def notify_human_only(lead: Lead, reason: str, user_message: str = "") -> None:
    """
    Apenas notifica o número humano via WhatsApp, sem alterar estágio do lead.
    Útil para perguntas não mapeadas durante script ativo.
    """
    if not settings.escalation_whatsapp_number:
        logger.warning("ESCALATION_WHATSAPP_NUMBER não configurado, aviso não foi enviado.")
        return

    escalation_to = _normalize_phone(settings.escalation_whatsapp_number)
    if not escalation_to:
        logger.warning("ESCALATION_WHATSAPP_NUMBER inválido após normalização.")
        return

    alert_message = (
        f"🟡 *Lead com pergunta para atendimento humano*\n\n"
        f"📱 *Número:* +{lead.phone_number}\n"
        f"👤 *Nome:* {lead.name or 'Não identificado'}\n"
        f"📚 *Curso:* {lead.course_slug.value}\n"
        f"📍 *Estágio:* {lead.stage.value}\n"
        f"📝 *Motivo:* {reason}\n"
        f"❓ *Pergunta:* {user_message or '(não informado)'}"
    )

    try:
        await whatsapp.send_text(
            to=escalation_to,
            text=alert_message,
        )
    except Exception as e:
        logger.error(
            "Falha ao enviar notificação humana (notify_human_only).",
            to=escalation_to,
            error=str(e),
        )


async def escalate(lead: Lead, reason: str = "Solicitado pelo lead") -> Lead:
    """
    Executa o fluxo de escalação:
    1. Atualiza o estágio do lead
    2. Notifica o número humano via WhatsApp
    3. Sincroniza com o SprintHub
    4. Avisa o lead que um consultor vai entrar em contato
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

    # 3. Notifica o número de suporte humano
    if not settings.escalation_whatsapp_number:
        logger.warning("ESCALATION_WHATSAPP_NUMBER não configurado, aviso não foi enviado.")
    else:
        escalation_to = _normalize_phone(settings.escalation_whatsapp_number)
        if not escalation_to:
            logger.warning("ESCALATION_WHATSAPP_NUMBER inválido após normalização.")
        else:
            alert_message = (
                f"🚨 *Novo lead aguardando atendimento humano!*\n\n"
                f"📱 *Número:* +{lead.phone_number}\n"
                f"👤 *Nome:* {lead.name or 'Não identificado'}\n"
                f"📚 *Curso de interesse:* {lead.course_slug.value}\n"
                f"📍 *Estágio:* {lead.stage.value}\n"
                f"📝 *Motivo:* {reason}\n\n"
                f"Por favor, entre em contato com o lead o quanto antes!"
            )
            try:
                await whatsapp.send_text(
                    to=escalation_to,
                    text=alert_message,
                )
            except Exception as e:
                logger.error(
                    "Falha ao enviar notificação humana (escalate).",
                    to=escalation_to,
                    error=str(e),
                )

    # 4. Sincroniza com CRM
    await crm.sync_lead(lead)

    return lead
