from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class CourseSlug(str, Enum):
    CURSO_1 = "curso_1"
    CURSO_2 = "curso_2"
    POS_FISIO_NEURO = "pos_fisio_neuro"
    UNKNOWN = "unknown"


class LeadStage(str, Enum):
    """Estágios do funil de vendas."""

    NEW = "new"  # Primeiro contato
    IDENTIFYING = "identifying"  # Identificando interesse/curso
    NURTURING = "nurturing"  # Recebendo script de áudios
    OBJECTION = "objection"  # Levantou objeção
    HOT = "hot"  # Demonstrou interesse forte
    NEGOTIATING = "negotiating"  # Discutindo preço/condições
    CONVERTED = "converted"  # Fechou / solicitou matrícula
    ESCALATED = "escalated"  # Transferido para humano
    LOST = "lost"  # Desistiu


class Lead(BaseModel):
    phone_number: str
    name: Optional[str] = None
    course_slug: CourseSlug = CourseSlug.UNKNOWN
    stage: LeadStage = LeadStage.NEW
    sprinthub_id: Optional[str] = None  # ID do card no SprintHub
    script_step: int = 0  # Qual passo do script de áudios está
    is_escalated: bool = False
    price_ask_count: int = 0  # Quantas vezes o lead pediu o preço durante o script
    last_received_msg_id: Optional[str] = None  # ID da última mensagem recebida (typing indicator)
    notes: Optional[str] = None  # Observações internas

    # Follow-up automático
    followup_enabled: bool = True
    followup_status: str = "idle"  # idle | running | stopped | finished
    followup_scenario: Optional[str] = None  # C1 | C2
    followup_step: int = 0
    followup_next_at: Optional[datetime] = None
    followup_anchor_at: Optional[datetime] = None  # início do silêncio (último outbound sem resposta)
    followup_started_at: Optional[datetime] = None
    followup_finished_at: Optional[datetime] = None
    followup_stopped_reason: Optional[str] = None

    # Controle de janela/fluxo
    last_inbound_at: Optional[datetime] = None  # última mensagem recebida do lead
    price_sent_at: Optional[datetime] = None  # quando o bloco de preço foi enviado
