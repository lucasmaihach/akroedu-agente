from pydantic import BaseModel, Field
from typing import Optional, List, Any


# ── Modelos de entrada do webhook da Meta ─────────────────────────────────────

class MetaTextMessage(BaseModel):
    body: str


class MetaAudioMessage(BaseModel):
    id: str
    mime_type: str


class MetaMessage(BaseModel):
    from_: str = Field(alias="from")
    id: str
    timestamp: str
    type: str  # "text" | "audio" | "image" | ...
    text: Optional[MetaTextMessage] = None
    audio: Optional[MetaAudioMessage] = None

    model_config = {"populate_by_name": True}


class MetaContact(BaseModel):
    profile: dict
    wa_id: str


class MetaValue(BaseModel):
    messaging_product: str
    metadata: dict
    contacts: Optional[List[MetaContact]] = None
    messages: Optional[List[MetaMessage]] = None
    statuses: Optional[List[Any]] = None


class MetaChange(BaseModel):
    value: MetaValue
    field: str


class MetaEntry(BaseModel):
    id: str
    changes: List[MetaChange]


class MetaWebhookPayload(BaseModel):
    object: str
    entry: List[MetaEntry]


# ── Modelo interno de mensagem processada ─────────────────────────────────────

class IncomingMessage(BaseModel):
    phone_number: str      # número do lead com DDI (ex: 5511999999999)
    message_id: str
    text: Optional[str] = None
    message_type: str = "text"
    timestamp: str
    contact_name: Optional[str] = None
