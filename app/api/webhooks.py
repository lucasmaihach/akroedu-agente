import asyncio
import structlog
from fastapi import APIRouter, Request, HTTPException

from app.config import settings
from app.models.message import MetaWebhookPayload, IncomingMessage
from app.memory.session import get_or_create_lead, is_message_already_processed
from app.agents.dispatcher import dispatch
from app.script.engine import run_script_step

logger = structlog.get_logger()

router = APIRouter()


# ── Verificação do webhook (handshake inicial) ──────────────────────────────

@router.get("/whatsapp")
async def verify_webhook(request: Request):
    """
    Endpoint de verificação do webhook (GET).
    Meta envia uma solicitação GET com query params para validar.
    """
    verify_token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if verify_token != settings.meta_verify_token:
        logger.warning("❌ Token de verificação inválido.")
        raise HTTPException(status_code=403, detail="Token inválido")

    logger.info("✅ Webhook verificado com sucesso.")
    return int(challenge)


# ── Recebimento de mensagens ────────────────────────────────────────────────

@router.post("/whatsapp")
async def receive_message(payload: MetaWebhookPayload):
    """
    Webhook que recebe mensagens do WhatsApp via Meta API.
    Processa de forma assíncrona para não bloquear a resposta.
    """
    try:
        # Meta espera resposta 200 imediatamente
        # Processamento acontece em background
        asyncio.create_task(_process_webhook(payload))
        return {"status": "received"}
    except Exception as e:
        logger.error("❌ Erro ao processar webhook.", error=str(e))
        return {"status": "error"}


async def _process_webhook(payload: MetaWebhookPayload):
    """
    Processamento assíncrono do webhook em background.
    """
    for entry in payload.entry:
        for change in entry.changes:
            value = change.value

            # Só processa mensagens, ignora status updates (lido, enviado, etc.)
            if not value.messages:
                continue

            # Processa cada mensagem
            for msg in value.messages:
                await _handle_incoming_message(msg, value)


async def _handle_incoming_message(msg, value) -> None:
    """
    Processa uma mensagem de entrada individual.
    """
    try:
        phone_number = msg.from_
        contact_name = value.contacts[0].profile.get("name") if value.contacts else None
        message_type = msg.type

        # Deduplicação: Meta pode reenviar o mesmo webhook mais de uma vez
        if await is_message_already_processed(msg.id):
            logger.info("Mensagem duplicada ignorada.", msg_id=msg.id, phone=phone_number)
            return

        logger.info(
            "📥 Nova mensagem recebida.",
            phone=phone_number,
            type=message_type,
            name=contact_name,
        )

        # Extrai o texto da mensagem (só processamos texto por enquanto)
        text = None
        if message_type == "text" and msg.text:
            text = msg.text.body.strip()
        else:
            # Se não for texto, ignora
            logger.info("Mensagem ignorada (tipo não é texto).", type=message_type)
            return

        # Obtém ou cria o lead
        lead = await get_or_create_lead(phone=phone_number, name=contact_name)

        # Dispara o agente para responder
        # (o histórico da mensagem do usuário é salvo dentro de dispatch/agent)
        await dispatch(lead=lead, user_message=text)

        # Agenda o próximo passo do script (se houver)
        asyncio.create_task(run_script_step(phone_number))

    except Exception as e:
        logger.error("❌ Erro ao processar mensagem.", error=str(e), exc_info=True)
