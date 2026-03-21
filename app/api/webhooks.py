import asyncio
import structlog
from fastapi import APIRouter, Request, HTTPException

from app.config import settings
from app.models.lead import CourseSlug, LeadStage
from app.models.message import MetaWebhookPayload
from app.memory.session import append_message, get_or_create_lead, is_message_already_processed
from app.services import whatsapp
from app.services.transcription import transcribe_audio
from app.followup.service import stop_followup_on_inbound
from app.services.error_alert import notify_conversation_error
from app.utils.business_hours import is_within_business_hours, now_utc
from app.jobs.store import schedule_debounce_inbound

logger = structlog.get_logger()

router = APIRouter()

INBOUND_ANALYSIS_DELAY_SECONDS = 30



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
            asyncio.create_task(
                notify_conversation_error(
                    source="meta.delivery_failed",
                    error=f"msg_id={msg_id} errors={errors}",
                    phone=recipient_id,
                    user_message="[outbound delivery failed]",
                    extra={"status": status, "timestamp": timestamp},
                )
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
                transcription = await transcribe_audio(
                    audio_bytes,
                    mime_type,
                    phone=phone_number,
                    lead_name=contact_name,
                )
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
                    await notify_conversation_error(
                        source="groq.transcription.empty",
                        error="Transcrição retornou vazia/None",
                        phone=phone_number,
                        lead_name=contact_name,
                        user_message="[áudio inbound]",
                    )
                    if is_within_business_hours(now_utc()):
                        await whatsapp.send_text(
                            to=phone_number,
                            text="Desculpa, não consegui ouvir bem. Pode mandar novamente? 😊"
                        )
                    else:
                        logger.info(
                            "🌙 Mensagem de falha de transcrição suprimida por fora do horário.",
                            phone=phone_number,
                        )
                    return
            except Exception as e:
                logger.error(
                    "❌ Erro ao processar áudio do lead.",
                    phone=phone_number,
                    error=str(e),
                )
                await notify_conversation_error(
                    source="webhook.audio_processing",
                    error=e,
                    phone=phone_number,
                    lead_name=contact_name,
                    user_message="[áudio inbound]",
                    extra={"message_type": message_type},
                )
                return

        else:
            # Outros tipos (imagem, vídeo, sticker, etc.) — ignora por enquanto
            logger.info("Mensagem ignorada (tipo não suportado).", type=message_type)
            if is_within_business_hours(now_utc()):
                await whatsapp.send_text(
                    to=phone_number,
                    text="Entendi! Por enquanto só consigo processar mensagens de texto e áudio. Pode escrever ou mandar um áudio? 😊"
                )
            else:
                logger.info(
                    "🌙 Mensagem de tipo não suportado suprimida por fora do horário.",
                    phone=phone_number,
                    type=message_type,
                )
            return

        # Registra a mensagem inbound no histórico (Redis + PostgreSQL)
        await append_message(phone_number, role="user", content=text)

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

        # Regra operacional: IA só atua para leads com produto/curso mapeado.
        # Se o lead não tiver produto válido, não entra no fluxo do agente.
        if lead.course_slug == CourseSlug.UNKNOWN:
            now = now_utc()
            should_notify_block = (
                not lead.last_unknown_prompt_at
                or (now - lead.last_unknown_prompt_at).total_seconds() > 24 * 3600
            )
            if should_notify_block and is_within_business_hours(now):
                await whatsapp.send_text(
                    to=phone_number,
                    text=(
                        "Oi! Este canal atende somente leads dos nossos produtos ativos. "
                        "Se você recebeu este número por engano, me avise que direciono ao time correto. 🙂"
                    ),
                )
                await _upd(phone_number, last_unknown_prompt_at=now)

            logger.info(
                "🚫 Lead sem produto mapeado: fluxo da IA bloqueado.",
                phone=phone_number,
                stage=lead.stage.value,
            )
            return

        # Qualquer inbound interrompe imediatamente a régua de follow-up.
        await stop_followup_on_inbound(lead=lead, user_message=text or "")

        # Debounce persistente: sobrevive restart e preserva janela de análise de 30s.
        await schedule_debounce_inbound(
            phone=phone_number,
            contact_name=contact_name,
            message_text=text or "",
            delay_seconds=INBOUND_ANALYSIS_DELAY_SECONDS,
        )

    except Exception as e:
        logger.error("❌ Erro ao processar mensagem.", error=str(e), exc_info=True)
        await notify_conversation_error(
            source="webhook.handle_incoming",
            error=e,
            phone=getattr(msg, "from_", None),
            user_message="[inbound processing]",
        )
