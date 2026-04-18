import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.services.chatwoot import mirror_outbound_message
from app.services.telemetry import increment_metric

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


def _normalize_phone(phone: str) -> str:
    """Normaliza telefone para formato esperado pela Meta (apenas dígitos)."""
    return "".join(ch for ch in phone if ch.isdigit())


MAX_WHATSAPP_BUBBLE_CHARS = 420
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_text_bubbles(text: str, max_chars: int = MAX_WHATSAPP_BUBBLE_CHARS) -> list[str]:
    """
    Quebra texto longo em bolhas curtas para WhatsApp:
    - preserva parágrafos quando possível
    - prioriza quebra por sentença
    - fallback por palavras quando necessário
    """
    clean_text = (text or "").strip()
    if not clean_text:
        return []

    paragraphs = [p.strip() for p in clean_text.split("\n") if p.strip()]
    chunks: list[str] = []

    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            chunks.append(paragraph)
            continue

        sentence_buffer = ""
        sentences = _SENTENCE_SPLIT_RE.split(paragraph)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            candidate = f"{sentence_buffer} {sentence}".strip() if sentence_buffer else sentence
            if len(candidate) <= max_chars:
                sentence_buffer = candidate
                continue

            if sentence_buffer:
                chunks.append(sentence_buffer)
                sentence_buffer = ""

            if len(sentence) <= max_chars:
                sentence_buffer = sentence
                continue

            words = sentence.split()
            word_buffer = ""
            for word in words:
                merged = f"{word_buffer} {word}".strip() if word_buffer else word
                if len(merged) <= max_chars:
                    word_buffer = merged
                    continue
                if word_buffer:
                    chunks.append(word_buffer)
                word_buffer = word
            if word_buffer:
                sentence_buffer = word_buffer

        if sentence_buffer:
            chunks.append(sentence_buffer)

    return chunks


def _is_missing_parameter_name_error(response: httpx.Response) -> bool:
    """
    Detecta erro permanente da Meta para templates com parâmetros incompatíveis.

    Exemplo observado em produção:
    "(#100) Invalid parameter" + details contendo "Parameter name is missing or empty".
    """
    if response.status_code != 400:
        return False

    body = (response.text or "").lower()
    if "parameter name is missing or empty" in body:
        return True

    try:
        payload = response.json()
    except Exception:
        return False

    error = payload.get("error") if isinstance(payload, dict) else None
    details = str((error or {}).get("error_data", {}).get("details", "")).lower()
    return "parameter name is missing or empty" in details


def _extract_missing_template_param_name(response: httpx.Response) -> str | None:
    """
    Extrai o nome do placeholder quando a Meta retorna erro:
    "Parameter name is missing for the parameter '{{customer_name}}'".
    """
    try:
        payload = response.json()
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    details = str((payload.get("error") or {}).get("error_data", {}).get("details", ""))
    marker_start = "{{"
    marker_end = "}}"
    if marker_start not in details or marker_end not in details:
        return None

    start = details.find(marker_start) + len(marker_start)
    end = details.find(marker_end, start)
    if end == -1:
        return None

    param_name = details[start:end].strip()
    return param_name or None


OUTBOUND_DEDUP_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 dias
OUTBOUND_DEDUP_LOCK_TTL_SECONDS = 120


def _outbound_done_key(dedup_key: str) -> str:
    return f"outbound:done:{dedup_key}"


def _outbound_lock_key(dedup_key: str) -> str:
    return f"outbound:lock:{dedup_key}"


def _extract_meta_message_id(response_payload: dict | None) -> str | None:
    if not isinstance(response_payload, dict):
        return None

    messages = response_payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return None

    first = messages[0]
    if not isinstance(first, dict):
        return None

    msg_id = first.get("id")
    return msg_id if isinstance(msg_id, str) and msg_id else None


async def _begin_outbound_send(dedup_key: str | None) -> tuple[str | None, dict | None]:
    if not dedup_key:
        return None, None

    from app.memory.session import get_redis

    redis = get_redis()
    done_key = _outbound_done_key(dedup_key)
    lock_key = _outbound_lock_key(dedup_key)

    if await redis.get(done_key):
        return None, {"status": "skipped", "reason": "idempotency_duplicate", "dedup_key": dedup_key}

    lock_token = str(uuid4())
    acquired = await redis.set(lock_key, lock_token, nx=True, ex=OUTBOUND_DEDUP_LOCK_TTL_SECONDS)
    if not acquired:
        raise RuntimeError(f"outbound_inflight:{dedup_key}")

    if await redis.get(done_key):
        await _release_outbound_lock(dedup_key, lock_token)
        return None, {"status": "skipped", "reason": "idempotency_duplicate", "dedup_key": dedup_key}

    return lock_token, None


async def _mark_outbound_sent(dedup_key: str, response_payload: dict | None) -> None:
    from app.memory.session import get_redis

    redis = get_redis()
    data = {
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "meta_message_id": _extract_meta_message_id(response_payload),
    }
    await redis.set(
        _outbound_done_key(dedup_key),
        json.dumps(data, ensure_ascii=False),
        ex=OUTBOUND_DEDUP_TTL_SECONDS,
    )


async def _release_outbound_lock(dedup_key: str, lock_token: str) -> None:
    from app.memory.session import get_redis

    redis = get_redis()
    key = _outbound_lock_key(dedup_key)
    current = await redis.get(key)
    if current and current == lock_token:
        await redis.delete(key)


async def _append_assistant_history(phone: str, content: str) -> None:
    """Registra outbound no histórico de conversa."""
    try:
        from app.memory.session import append_message

        await append_message(phone, role="assistant", content=content)
    except Exception as e:
        logger.warning("⚠️ Falha ao registrar outbound no histórico.", phone=phone, error=str(e))


async def record_outbound_event(phone: str, content: str) -> None:
    """API pública para registrar eventos outbound customizados no histórico."""
    phone = _normalize_phone(phone)
    await _append_assistant_history(phone, content)


# ── Envio de mensagens ────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def send_text(to: str, text: str, dedup_key: str | None = None) -> dict:
    """Envia uma mensagem de texto simples."""
    to = _normalize_phone(to)
    lock_token: str | None = None

    try:
        lock_token, skipped = await _begin_outbound_send(dedup_key)
        if skipped:
            logger.info("⏭️ Texto outbound deduplicado.", to=to, dedup_key=dedup_key)
            return skipped

        payload = {
            **_base_payload(to),
            "type": "text",
            "text": {"body": text, "preview_url": False},
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
            resp.raise_for_status()
            body = resp.json()
            if dedup_key:
                await _mark_outbound_sent(dedup_key, body)
            logger.info("📤 Texto enviado.", to=to, preview=text[:60])
            await _append_assistant_history(to, text)
            await mirror_outbound_message(to, text)
            await increment_metric("messages_responded_total", tags={"channel": "whatsapp", "type": "text"})
            return body
    except Exception:
        await increment_metric("messages_response_failed_total", tags={"channel": "whatsapp", "type": "text"})
        await increment_metric("conversation_error_total", tags={"category": "send_error", "channel": "whatsapp", "type": "text"})
        raise
    finally:
        if dedup_key and lock_token:
            await _release_outbound_lock(dedup_key, lock_token)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def send_template(
    to: str,
    template_name: str,
    language_code: str = "pt_BR",
    body_params: list[str] | None = None,
    dedup_key: str | None = None,
) -> dict:
    """
    Envia mensagem template (HSM), usada para outbound fora da janela de 24h.

    body_params preenche placeholders do body do template na ordem aprovada pela Meta.
    """
    to = _normalize_phone(to)

    components: list[dict] = []
    if body_params:
        components.append(
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": param}
                    for param in body_params
                ],
            }
        )

    template_payload: dict = {
        "name": template_name,
        "language": {"code": language_code},
    }
    if components:
        template_payload["components"] = components

    lock_token: str | None = None

    try:
        lock_token, skipped = await _begin_outbound_send(dedup_key)
        if skipped:
            logger.info("⏭️ Template outbound deduplicado.", to=to, dedup_key=dedup_key, template=template_name)
            return skipped

        payload = {
            **_base_payload(to),
            "type": "template",
            "template": template_payload,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(BASE_URL, json=payload, headers=HEADERS)

            # Compatibilidade: templates com placeholders nomeados exigem
            # parameter_name em cada parâmetro.
            if body_params and _is_missing_parameter_name_error(resp):
                missing_name = _extract_missing_template_param_name(resp)
                logger.warning(
                    "⚠️ Template exige parâmetros nomeados; tentando reenvio com parameter_name.",
                    template=template_name,
                    to=to,
                    missing_param_name=missing_name,
                    status=resp.status_code,
                    body=resp.text[:220],
                )
                if len(body_params) != 1:
                    resp.raise_for_status()
                if not missing_name:
                    missing_name = "customer_name"
                fallback_payload = {
                    **_base_payload(to),
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {"code": language_code},
                        "components": [
                            {
                                "type": "body",
                                "parameters": [
                                    {
                                        "type": "text",
                                        "parameter_name": missing_name,
                                        "text": body_params[0],
                                    }
                                ],
                            }
                        ],
                    },
                }
                resp = await client.post(BASE_URL, json=fallback_payload, headers=HEADERS)

            resp.raise_for_status()
            body = resp.json()
            if dedup_key:
                await _mark_outbound_sent(dedup_key, body)
            logger.info(
                "📤 Template enviado.",
                to=to,
                template=template_name,
                language=language_code,
                params_count=len(body_params or []),
            )
            template_preview = f"[template] {template_name}"
            if body_params:
                template_preview += f" | params: {' | '.join(body_params)}"
            await _append_assistant_history(to, template_preview)
            await mirror_outbound_message(to, template_preview)
            await increment_metric("messages_responded_total", tags={"channel": "whatsapp", "type": "template"})
            return body
    except Exception:
        await increment_metric("messages_response_failed_total", tags={"channel": "whatsapp", "type": "template"})
        await increment_metric("conversation_error_total", tags={"category": "send_error", "channel": "whatsapp", "type": "template"})
        raise
    finally:
        if dedup_key and lock_token:
            await _release_outbound_lock(dedup_key, lock_token)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def send_audio_by_url(
    to: str,
    audio_url: str,
    history_label: str | None = "[áudio enviado]",
    dedup_key: str | None = None,
) -> dict:
    """
    Envia um áudio a partir de uma URL pública como mensagem de voz (PTT).
    Aparece com ondas de voz no WhatsApp, igual a um áudio gravado pelo celular.
    O arquivo na URL deve estar em formato OGG/OPUS para renderizar como PTT.
    """
    payload = {
        **_base_payload(to),
        "type": "audio",
        "audio": {"link": audio_url, "voice": True},
    }
    lock_token: str | None = None
    try:
        lock_token, skipped = await _begin_outbound_send(dedup_key)
        if skipped:
            logger.info("⏭️ Áudio outbound deduplicado (url).", to=to, dedup_key=dedup_key)
            return skipped

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
            resp.raise_for_status()
            body = resp.json()
            if dedup_key:
                await _mark_outbound_sent(dedup_key, body)
            logger.info("🎤 Áudio PTT enviado por URL.", to=to, url=audio_url)
            if history_label:
                await _append_assistant_history(to, history_label)
                await mirror_outbound_message(to, history_label)
            await increment_metric("messages_responded_total", tags={"channel": "whatsapp", "type": "audio"})
            return body
    except Exception:
        await increment_metric("messages_response_failed_total", tags={"channel": "whatsapp", "type": "audio"})
        await increment_metric("conversation_error_total", tags={"category": "send_error", "channel": "whatsapp", "type": "audio"})
        raise
    finally:
        if dedup_key and lock_token:
            await _release_outbound_lock(dedup_key, lock_token)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def send_audio_by_media_id(
    to: str,
    media_id: str,
    history_label: str | None = "[áudio enviado]",
    dedup_key: str | None = None,
) -> dict:
    """
    Envia um áudio usando um media_id já hospedado na Meta como mensagem de voz (PTT).
    Aparece com ondas de voz no WhatsApp, igual a um áudio gravado pelo celular.
    O arquivo deve estar em formato OGG/OPUS para renderizar como PTT.
    """
    payload = {
        **_base_payload(to),
        "type": "audio",
        "audio": {"id": media_id, "voice": True},
    }
    lock_token: str | None = None
    try:
        lock_token, skipped = await _begin_outbound_send(dedup_key)
        if skipped:
            logger.info("⏭️ Áudio outbound deduplicado (media_id).", to=to, dedup_key=dedup_key)
            return skipped

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
            resp.raise_for_status()
            body = resp.json()
            if dedup_key:
                await _mark_outbound_sent(dedup_key, body)
            logger.info("🎤 Áudio PTT enviado por media_id.", to=to, media_id=media_id)
            if history_label:
                await _append_assistant_history(to, history_label)
                await mirror_outbound_message(to, history_label)
            await increment_metric("messages_responded_total", tags={"channel": "whatsapp", "type": "audio"})
            return body
    except Exception:
        await increment_metric("messages_response_failed_total", tags={"channel": "whatsapp", "type": "audio"})
        await increment_metric("conversation_error_total", tags={"category": "send_error", "channel": "whatsapp", "type": "audio"})
        raise
    finally:
        if dedup_key and lock_token:
            await _release_outbound_lock(dedup_key, lock_token)


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
async def send_image_by_media_id(
    to: str,
    media_id: str,
    caption: str = "",
    dedup_key: str | None = None,
) -> dict:
    """Envia uma imagem usando um media_id já hospedado na Meta."""
    image_payload: dict = {"id": media_id}
    if caption:
        image_payload["caption"] = caption
    payload = {
        **_base_payload(to),
        "type": "image",
        "image": image_payload,
    }
    lock_token: str | None = None
    try:
        lock_token, skipped = await _begin_outbound_send(dedup_key)
        if skipped:
            logger.info("⏭️ Imagem outbound deduplicada (media_id).", to=to, dedup_key=dedup_key)
            return skipped

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
            resp.raise_for_status()
            body = resp.json()
            if dedup_key:
                await _mark_outbound_sent(dedup_key, body)
            logger.info("🖼 Imagem enviada por media_id.", to=to, media_id=media_id)
            caption_preview = f"[imagem enviada] {caption}".strip()
            await _append_assistant_history(to, caption_preview)
            await mirror_outbound_message(to, caption_preview)
            await increment_metric("messages_responded_total", tags={"channel": "whatsapp", "type": "image"})
            return body
    except Exception:
        await increment_metric("messages_response_failed_total", tags={"channel": "whatsapp", "type": "image"})
        await increment_metric("conversation_error_total", tags={"category": "send_error", "channel": "whatsapp", "type": "image"})
        raise
    finally:
        if dedup_key and lock_token:
            await _release_outbound_lock(dedup_key, lock_token)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def send_image_by_url(
    to: str,
    image_url: str,
    caption: str = "",
    dedup_key: str | None = None,
) -> dict:
    """Envia uma imagem a partir de uma URL pública."""
    image_payload: dict = {"link": image_url}
    if caption:
        image_payload["caption"] = caption
    payload = {
        **_base_payload(to),
        "type": "image",
        "image": image_payload,
    }
    lock_token: str | None = None
    try:
        lock_token, skipped = await _begin_outbound_send(dedup_key)
        if skipped:
            logger.info("⏭️ Imagem outbound deduplicada (url).", to=to, dedup_key=dedup_key)
            return skipped

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
            resp.raise_for_status()
            body = resp.json()
            if dedup_key:
                await _mark_outbound_sent(dedup_key, body)
            logger.info("🖼 Imagem enviada por URL.", to=to, url=image_url)
            caption_preview = f"[imagem enviada] {caption}".strip()
            await _append_assistant_history(to, caption_preview)
            await mirror_outbound_message(to, caption_preview)
            await increment_metric("messages_responded_total", tags={"channel": "whatsapp", "type": "image"})
            return body
    except Exception:
        await increment_metric("messages_response_failed_total", tags={"channel": "whatsapp", "type": "image"})
        await increment_metric("conversation_error_total", tags={"category": "send_error", "channel": "whatsapp", "type": "image"})
        raise
    finally:
        if dedup_key and lock_token:
            await _release_outbound_lock(dedup_key, lock_token)


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


async def send_typing_indicator(message_id: str) -> None:
    """
    Envia o indicador de digitação ('Digitando...') para o lead.
    Requer o ID da última mensagem recebida.
    O indicador dura até 25 segundos ou até o envio da próxima mensagem.
    Falhas são ignoradas silenciosamente (é um detalhe cosmético).
    """
    if not message_id:
        return
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {"type": "text"},
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
            resp.raise_for_status()
            logger.debug("⌨️ Typing indicator enviado.", msg_id=message_id)
    except Exception as e:
        logger.debug("⌨️ Typing indicator falhou (ignorado).", error=str(e))


async def send_recording_indicator(message_id: str) -> None:
    """
    Envia o indicador de gravação de áudio ('Gravando áudio...') para o lead.
    Tenta type=audio primeiro; se a Meta rejeitar, cai para type=text.
    Falhas são ignoradas silenciosamente (é um detalhe cosmético).
    """
    if not message_id:
        return

    for indicator_type in ("audio", "text"):
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
            "typing_indicator": {"type": indicator_type},
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
                if resp.status_code < 300:
                    logger.info("🎙️ Recording indicator enviado.", msg_id=message_id, type=indicator_type)
                    return
                # type=audio pode ser rejeitado pela Meta — tenta type=text como fallback
                logger.info(
                    "🎙️ Recording indicator falhou, tentando fallback.",
                    type=indicator_type,
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as e:
            logger.info("🎙️ Recording indicator erro, tentando fallback.", type=indicator_type, error=str(e))


async def send_recording_and_wait(message_id: str, duration_seconds: float) -> None:
    """
    Mostra o indicador de gravação de áudio e aguarda antes de enviar.
    Para durações acima de 24s, reenvia o indicador antes de expirar.
    """
    import asyncio
    remaining = max(0.5, duration_seconds)
    while remaining > 0:
        await send_recording_indicator(message_id)
        chunk = min(remaining, 24.0)
        await asyncio.sleep(chunk)
        remaining -= chunk


async def send_reaction(to: str, message_id: str, emoji: str = "❤️") -> None:
    """
    Reage a uma mensagem do lead com um emoji.
    Falhas são ignoradas silenciosamente (é um detalhe cosmético).
    """
    if not message_id:
        return
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "reaction",
        "reaction": {
            "message_id": message_id,
            "emoji": emoji,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                BASE_URL,
                json=payload,
                headers=HEADERS,
            )
            resp.raise_for_status()
            logger.debug("❤️ Reação enviada.", to=to, msg_id=message_id, emoji=emoji)
    except Exception as e:
        logger.debug("❤️ Reação falhou (ignorado).", error=str(e))


async def send_typing_and_wait(message_id: str, duration_seconds: float) -> None:
    """
    Mostra o indicador de digitação e aguarda o tempo necessário antes de enviar.
    Para durações acima de 24s, reenvia o indicador antes de expirar.
    """
    import asyncio
    remaining = max(0.5, duration_seconds)
    while remaining > 0:
        await send_typing_indicator(message_id)
        chunk = min(remaining, 24.0)
        await asyncio.sleep(chunk)
        remaining -= chunk


def estimate_typing_delay(text: str) -> float:
    """
    Estima o tempo de digitação humano para um texto.
    Baseado em ~4 caracteres/segundo no celular.
    Mínimo 1.5s, máximo 12s.
    """
    delay = len(text) * 0.25  # 4 chars/s
    return max(1.5, min(12.0, delay))
