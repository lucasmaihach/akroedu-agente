import asyncio
import structlog
from fastapi import APIRouter, Request, HTTPException

from app.config import settings
from app.models.lead import LeadStage
from app.models.message import MetaWebhookPayload
from app.memory.session import get_or_create_lead, is_message_already_processed
from app.agents.dispatcher import dispatch
from app.script.engine import run_script_step
from app.services import whatsapp
from app.services.transcription import transcribe_audio
from app.followup.service import stop_followup_on_inbound

logger = structlog.get_logger()

router = APIRouter()


def _log_status_updates(value) -> None:
    """Registra status de entrega das mensagens enviadas pela Meta."""
    if not value.statuses:
        return

    for st in value.statuses:
        status = st.get("status", "unknown")
        msg_id = st.get("id", "")
        recipient_id = st.get("recipient_id", "")
        timestamp = st.get("timestamp", "")
        errors = st.get("errors") or []

        if status in {"sent", "delivered", "read"}:
            logger.info(
                "📬 Status de mensagem WhatsApp.",
                status=status,
                msg_id=msg_id,
                recipient=recipient_id,
                timestamp=timestamp,
            )
        elif status == "failed":
            logger.error(
                "❌ Falha na entrega de mensagem WhatsApp.",
                status=status,
                msg_id=msg_id,
                recipient=recipient_id,
                timestamp=timestamp,
                errors=errors,
            )
        else:
            logger.info(
                "ℹ️ Atualização de status WhatsApp.",
                status=status,
                msg_id=msg_id,
                recipient=recipient_id,
                timestamp=timestamp,
            )


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

            # Registra status de entrega (sent/delivered/read/failed)
            _log_status_updates(value)

            # Processa mensagens recebidas do lead (se existirem)
            if value.messages:
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

        # Extrai o texto da mensagem
        text = None

        if message_type == "text" and msg.text:
            text = msg.text.body.strip()

        elif message_type == "audio" and msg.audio:
            # Baixa o áudio da Meta e transcreve via Groq Whisper
            try:
                audio_bytes, mime_type = await whatsapp.download_media(msg.audio.id)
                transcription = await transcribe_audio(audio_bytes, mime_type)
                if transcription:
                    text = f"[áudio]: {transcription}"
                    logger.info(
                        "🎙️ Áudio do lead transcrito.",
                        phone=phone_number,
                        transcription_preview=transcription[:80],
                    )
                else:
                    logger.warning(
                        "⚠️ Transcrição falhou — áudio ignorado.",
                        phone=phone_number,
                    )
                    await whatsapp.send_text(
                        to=phone_number,
                        text="Desculpa, não consegui ouvir bem. Pode mandar novamente? 😊"
                    )
                    return
            except Exception as e:
                logger.error(
                    "❌ Erro ao processar áudio do lead.",
                    phone=phone_number,
                    error=str(e),
                )
                return

        else:
            # Outros tipos (imagem, vídeo, sticker, etc.) — ignora por enquanto
            logger.info("Mensagem ignorada (tipo não suportado).", type=message_type)
            await whatsapp.send_text(
                to=phone_number,
                text="Entendi! Por enquanto só consigo processar mensagens de texto e áudio. Pode escrever ou mandar um áudio? 😊"
            )
            return

        # Obtém ou cria o lead e salva o ID da mensagem recebida (usado para typing indicator)
        from app.memory.session import update_lead_field as _upd
        lead = await get_or_create_lead(phone=phone_number, name=contact_name)

        update_kwargs = {"last_received_msg_id": msg.id}
        if lead.awaiting_template_reply:
            update_kwargs["awaiting_template_reply"] = False

            # Quando o lead responde ao template inicial enviado pelo CRM,
            # pulamos o BLOCO 1 (apresentação) para evitar repetição de boas-vindas.
            if lead.stage == LeadStage.NURTURING and lead.script_step == 0:
                update_kwargs["script_step"] = 1

        lead = await _upd(phone_number, **update_kwargs)

        # Qualquer inbound interrompe imediatamente a régua de follow-up.
        await stop_followup_on_inbound(lead=lead, user_message=text or "")

        # Recarrega lead atualizado antes de seguir o fluxo principal.
        lead = await get_or_create_lead(phone=phone_number, name=contact_name)

        # Dispara o agente para responder
        # (o histórico da mensagem do usuário é salvo dentro de dispatch/agent)
        # dispatch() retorna True se o script deve avançar, False se ele foi pausado
        # (ex: quando intercepta pergunta de preço na 1ª vez)
        should_advance_script = await dispatch(lead=lead, user_message=text)

        # Agenda o próximo passo do script apenas se o dispatch autorizou
        if should_advance_script:
            asyncio.create_task(run_script_step(phone_number))

    except Exception as e:
        logger.error("❌ Erro ao processar mensagem.", error=str(e), exc_info=True)
