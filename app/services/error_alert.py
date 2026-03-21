from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import Request

from app.config import settings
from app.services import whatsapp

logger = structlog.get_logger()


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def _extract_phone_from_body(body: bytes) -> str | None:
    """Tenta extrair telefone do payload do webhook WhatsApp/CRM para contexto do alerta."""
    if not body:
        return None

    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        return None

    # WhatsApp webhook shape: entry[].changes[].value.messages[].from
    try:
        entries = data.get("entry") or []
        for entry in entries:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                messages = value.get("messages") or []
                if messages and isinstance(messages[0], dict):
                    phone = messages[0].get("from")
                    if phone:
                        return _normalize_phone(str(phone))
    except Exception:
        pass

    # WhatsApp contacts fallback
    try:
        entries = data.get("entry") or []
        for entry in entries:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                contacts = value.get("contacts") or []
                if contacts and isinstance(contacts[0], dict):
                    wa_id = contacts[0].get("wa_id")
                    if wa_id:
                        return _normalize_phone(str(wa_id))
    except Exception:
        pass

    # CRM payloads comuns
    candidates = [
        data.get("phone"),
        data.get("phone_number"),
        ((data.get("lead") or {}).get("phone") if isinstance(data.get("lead"), dict) else None),
    ]
    for c in candidates:
        if c:
            normalized = _normalize_phone(str(c))
            if normalized:
                return normalized

    return None


def _sanitize_query(query: str) -> str:
    # evita vazar key/token em alerta
    query = re.sub(r"([?&](?:key|token|access_token|x-admin-key)=)[^&]+", r"\1***", query, flags=re.I)
    return query


async def notify_api_error(
    request: Request,
    *,
    status_code: int,
    error: Exception | None = None,
    duration_ms: int | None = None,
    request_body: bytes = b"",
) -> None:
    """Dispara alerta de erro da API via WhatsApp para o número de escalação."""
    escalation_to = _normalize_phone(settings.escalation_whatsapp_number or "")
    if not escalation_to:
        return

    try:
        now = datetime.now(timezone.utc).isoformat()
        method = request.method
        url_path = request.url.path
        query = _sanitize_query(request.url.query or "")
        full_path = f"{url_path}?{query}" if query else url_path
        client_ip = request.client.host if request.client else "unknown"
        phone = _extract_phone_from_body(request_body)
        error_text = (str(error) if error else f"HTTP {status_code}")[:700]
        body_preview = (request_body.decode("utf-8", errors="ignore")[:500] if request_body else "")

        message = (
            "🚨 *Erro na API (produção)*\n\n"
            f"🕒 *Quando:* {now}\n"
            f"📍 *Rota:* {method} {full_path}\n"
            f"🔢 *Status:* {status_code}\n"
            f"🌐 *IP:* {client_ip}\n"
            f"📱 *Lead:* +{phone if phone else 'não identificado'}\n"
            f"⏱ *Duração:* {duration_ms if duration_ms is not None else '-'} ms\n"
            f"❌ *Erro:* {error_text}\n"
            f"📦 *Payload (preview):* {body_preview or '(vazio)'}"
        )

        await whatsapp.send_text(to=escalation_to, text=message)
    except Exception as e:
        logger.error("Falha ao enviar alerta de erro da API.", error=str(e))


async def notify_conversation_error(
    *,
    source: str,
    error: Exception | str,
    phone: str | None = None,
    lead_name: str | None = None,
    stage: str | None = None,
    user_message: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Alerta para falhas que impactam conversa com o lead (IA, transcrição, envio, etc.)."""
    escalation_to = _normalize_phone(settings.escalation_whatsapp_number or "")
    if not escalation_to:
        return

    try:
        now = datetime.now(timezone.utc).isoformat()
        clean_phone = _normalize_phone(phone or "")
        error_text = str(error)[:700]
        msg_preview = (user_message or "").strip()[:240]

        details = ""
        if extra:
            for k, v in extra.items():
                details += f"\n• {k}: {str(v)[:180]}"

        message = (
            "🚨 *Erro que impacta conversa com lead*\n\n"
            f"🕒 *Quando:* {now}\n"
            f"🧩 *Origem:* {source}\n"
            f"📱 *Lead:* +{clean_phone if clean_phone else 'não identificado'}\n"
            f"👤 *Nome:* {lead_name or 'não identificado'}\n"
            f"📍 *Estágio:* {stage or '-'}\n"
            f"💬 *Mensagem do lead:* {msg_preview or '-'}\n"
            f"❌ *Erro:* {error_text}"
            f"{details}"
        )

        await whatsapp.send_text(to=escalation_to, text=message)
    except Exception as e:
        logger.error("Falha ao enviar alerta de erro de conversa.", error=str(e))
