from pydantic import BaseModel
from typing import Optional
from enum import Enum


class CourseSlug(str, Enum):
    CURSO_1 = "curso_1"
    CURSO_2 = "curso_2"
    POS_FISIO_NEURO = "pos_fisio_neuro"
    UNKNOWN = "unknown"


class LeadStage(str, Enum):
    """Estágios do funil de vendas."""
    NEW = "new"                          # Primeiro contato
    IDENTIFYING = "identifying"          # Identificando interesse/curso
    NURTURING = "nurturing"              # Recebendo script de áudios
    OBJECTION = "objection"              # Levantou objeção
    HOT = "hot"                          # Demonstrou interesse forte
    NEGOTIATING = "negotiating"          # Discutindo preço/condições
    CONVERTED = "converted"              # Fechou / solicitou matrícula
    ESCALATED = "escalated"             # Transferido para humano
    LOST = "lost"                        # Desistiu


class Lead(BaseModel):
    phone_number: str
    name: Optional[str] = None
    course_slug: CourseSlug = CourseSlug.UNKNOWN
    stage: LeadStage = LeadStage.NEW
    sprinthub_id: Optional[str] = None   # ID do card no SprintHub
    script_step: int = 0                  # Qual passo do script de áudios está
    is_escalated: bool = False
    notes: Optional[str] = None          # Observações internas
