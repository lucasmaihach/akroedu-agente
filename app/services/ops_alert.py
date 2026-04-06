from __future__ import annotations

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


async def send_internal_alert(text: str) -> bool:
    """
    Envia alerta interno para canal de operações.
    Atualmente usa Telegram (bot + chat_id). Se não estiver configurado,
    apenas registra warning e não envia para o lead.
    """
    token = (settings.telegram_bot_token or "").strip()
    chat_id = (settings.telegram_chat_id or "").strip()

    if not token or not chat_id:
        logger.warning(
            "Canal interno de operações (Telegram) não configurado.",
            has_token=bool(token),
            has_chat_id=bool(chat_id),
        )
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        return True
    except Exception as e:
        logger.error("Falha ao enviar alerta interno no Telegram.", error=str(e))
        return False

