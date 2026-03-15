import httpx
import structlog
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = structlog.get_logger()

BASE_URL = f"{settings.meta_api_url}/{settings.meta_phone_number_id}/messages"
MEDIA_URL = f"{settings.meta_api_url}/{settings.meta_phone_number_id}/media"

HEADERS = {
    "Authorization": f"Bearer {settings.meta_access_token}",
    "Content-Type": "application/json",
}


# ── Helpers internos ──────────────────────────────────────────────────────────

def _base_payload(to: str) -> dict:
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
    }


# ── Envio de mensagens ────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def send_text(to: str, text: str) -> dict:
    """Envia uma mensagem de texto simples."""
    payload = {
        **_base_payload(to),
        "type": "text",
        "text": {"body": text, "preview_url": False},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()
        logger.info("📤 Texto enviado.", to=to, preview=text[:60])
        return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def send_audio_by_url(to: str, audio_url: str) -> dict:
    """
    Envia um áudio a partir de uma URL pública como mensagem de voz (PTT).
    Aparece com ondas de voz no WhatsApp, igual a um áudio gravado pelo celular.
    O arquivo na URL deve estar em formato OGG/OPUS para renderizar como PTT.
    """
    payload = {
        **_base_payload(to),
        "type": "audio",
        "audio": {"link": audio_url},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()
        logger.info("🎤 Áudio PTT enviado por URL.", to=to, url=audio_url)
        return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def send_audio_by_media_id(to: str, media_id: str) -> dict:
    """
    Envia um áudio usando um media_id já hospedado na Meta como mensagem de voz (PTT).
    Aparece com ondas de voz no WhatsApp, igual a um áudio gravado pelo celular.
    O arquivo deve estar em formato OGG/OPUS para renderizar como PTT.
    """
    payload = {
        **_base_payload(to),
        "type": "audio",
        "audio": {"id": media_id},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()
        logger.info("🎤 Áudio PTT enviado por media_id.", to=to, media_id=media_id)
        return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def upload_audio(file_path: str) -> str:
    """
    Faz upload de um arquivo de áudio local para a API da Meta.
    Retorna o media_id para ser reutilizado em envios futuros.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {file_path}")

    # Detecta o mime type pelo extension
    # WhatsApp aceita: audio/aac, audio/mp4, audio/mpeg, audio/amr, audio/ogg;codecs=opus
    mime_map = {
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".opus": "audio/ogg; codecs=opus",  # obrigatório para WhatsApp renderizar como PTT
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".aac": "audio/aac",
        ".amr": "audio/amr",
    }
    mime_type = mime_map.get(path.suffix.lower(), "audio/mpeg")

    headers = {"Authorization": f"Bearer {settings.meta_access_token}"}

    async with httpx.AsyncClient(timeout=60) as client:
        with open(path, "rb") as f:
            resp = await client.post(
                MEDIA_URL,
                headers=headers,
                data={"messaging_product": "whatsapp"},
                files={"file": (path.name, f, mime_type)},
            )
        resp.raise_for_status()
        media_id = resp.json()["id"]
        logger.info("📁 Áudio enviado para a Meta.", filename=path.name, media_id=media_id)
        return media_id


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def upload_image(file_path: str) -> str:
    """
    Faz upload de um arquivo de imagem local para a API da Meta.
    Retorna o media_id para ser reutilizado em envios futuros.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de imagem não encontrado: {file_path}")

    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(path.suffix.lower(), "image/jpeg")

    headers = {"Authorization": f"Bearer {settings.meta_access_token}"}

    async with httpx.AsyncClient(timeout=60) as client:
        with open(path, "rb") as f:
            resp = await client.post(
                MEDIA_URL,
                headers=headers,
                data={"messaging_product": "whatsapp"},
                files={"file": (path.name, f, mime_type)},
            )
        resp.raise_for_status()
        media_id = resp.json()["id"]
        logger.info("🖼 Imagem enviada para a Meta.", filename=path.name, media_id=media_id)
        return media_id


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def send_image_by_media_id(to: str, media_id: str, caption: str = "") -> dict:
    """Envia uma imagem usando um media_id já hospedado na Meta."""
    image_payload: dict = {"id": media_id}
    if caption:
        image_payload["caption"] = caption
    payload = {
        **_base_payload(to),
        "type": "image",
        "image": image_payload,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()
        logger.info("🖼 Imagem enviada por media_id.", to=to, media_id=media_id)
        return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def send_image_by_url(to: str, image_url: str, caption: str = "") -> dict:
    """Envia uma imagem a partir de uma URL pública."""
    image_payload: dict = {"link": image_url}
    if caption:
        image_payload["caption"] = caption
    payload = {
        **_base_payload(to),
        "type": "image",
        "image": image_payload,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()
        logger.info("🖼 Imagem enviada por URL.", to=to, url=image_url)
        return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def mark_as_read(message_id: str) -> None:
    """Marca uma mensagem como lida (✓✓ azul)."""
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()


async def download_media(media_id: str) -> tuple[bytes, str]:
    """
    Baixa um arquivo de mídia da Meta pelo media_id.
    Retorna (bytes_do_arquivo, mime_type).

    Usado para baixar áudios enviados pelo lead e transcrever.
    """
    # Passo 1: obtém a URL de download pelo media_id
    headers_auth = {"Authorization": f"Bearer {settings.meta_access_token}"}
    media_info_url = f"{settings.meta_api_url}/{media_id}"

    async with httpx.AsyncClient(timeout=15) as client:
        info_resp = await client.get(media_info_url, headers=headers_auth)
        info_resp.raise_for_status()
        info = info_resp.json()

    download_url = info.get("url")
    mime_type = info.get("mime_type", "audio/ogg")

    if not download_url:
        raise ValueError(f"URL de download não encontrada para media_id={media_id}")

    # Passo 2: baixa o arquivo de mídia
    async with httpx.AsyncClient(timeout=60) as client:
        dl_resp = await client.get(download_url, headers=headers_auth)
        dl_resp.raise_for_status()
        audio_bytes = dl_resp.content

    logger.info(
        "⬇️ Mídia baixada da Meta.",
        media_id=media_id,
        mime_type=mime_type,
        size_kb=len(audio_bytes) // 1024,
    )
    return audio_bytes, mime_type


async def send_typing_indicator(to: str) -> None:
    """
    Simula digitação — envia status 'typing'.
    A API oficial não suporta diretamente, mas podemos
    usar um pequeno delay antes do envio para simular efeito humano.
    """
    import asyncio
    await asyncio.sleep(1.5)  # simula pausa antes de responder
