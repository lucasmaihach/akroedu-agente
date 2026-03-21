"""
Transcrição de áudio via Groq (Whisper).

Groq oferece transcrição gratuita com até 7.200 segundos/dia.
Modelo: whisper-large-v3-turbo (rápido e preciso para português).

Uso:
    text = await transcribe_audio(audio_bytes, mime_type="audio/ogg; codecs=opus")
    # retorna o texto transcrito ou None se falhar
"""
import io
import structlog
import httpx

from app.config import settings
from app.services.error_alert import notify_conversation_error

logger = structlog.get_logger()

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


async def transcribe_audio(
    audio_bytes: bytes,
    mime_type: str = "audio/ogg",
    *,
    phone: str | None = None,
    lead_name: str | None = None,
) -> str | None:
    """
    Transcreve um arquivo de áudio usando Groq Whisper.

    Args:
        audio_bytes: bytes do arquivo de áudio
        mime_type: tipo MIME do áudio (ex: "audio/ogg; codecs=opus", "audio/mp4")

    Returns:
        Texto transcrito ou None se a transcrição falhar / Groq não estiver configurado.
    """
    if not settings.groq_api_key:
        logger.warning("⚠️ GROQ_API_KEY não configurado — transcrição desativada.")
        return None

    # Determina extensão do arquivo pelo mime_type
    ext_map = {
        "audio/ogg": "ogg",
        "audio/ogg; codecs=opus": "ogg",
        "audio/mpeg": "mp3",
        "audio/mp4": "mp4",
        "audio/wav": "wav",
        "audio/webm": "webm",
        "audio/aac": "aac",
        "audio/amr": "amr",
    }
    ext = ext_map.get(mime_type.lower().strip(), "ogg")
    filename = f"audio.{ext}"

    try:
        headers = {"Authorization": f"Bearer {settings.groq_api_key}"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                GROQ_TRANSCRIPTION_URL,
                headers=headers,
                files={"file": (filename, io.BytesIO(audio_bytes), mime_type)},
                data={
                    "model": "whisper-large-v3-turbo",
                    "language": "pt",
                    "response_format": "text",
                },
            )
            resp.raise_for_status()
            transcription = resp.text.strip()
            logger.info(
                "🎙️ Áudio transcrito com sucesso.",
                chars=len(transcription),
                preview=transcription[:80],
            )
            return transcription

    except httpx.HTTPStatusError as e:
        logger.error(
            "❌ Erro HTTP ao transcrever áudio via Groq.",
            status=e.response.status_code,
            body=e.response.text[:200],
        )
        await notify_conversation_error(
            source="groq.transcription.http",
            error=f"status={e.response.status_code} body={e.response.text[:200]}",
            phone=phone,
            lead_name=lead_name,
            user_message="[áudio inbound]",
            extra={"mime_type": mime_type},
        )
        return None
    except Exception as e:
        logger.error("❌ Erro inesperado na transcrição.", error=str(e))
        await notify_conversation_error(
            source="groq.transcription.unexpected",
            error=e,
            phone=phone,
            lead_name=lead_name,
            user_message="[áudio inbound]",
            extra={"mime_type": mime_type},
        )
        return None
