import httpx
import structlog
from typing import Optional

from app.config import settings
from app.models.lead import Lead, LeadStage

logger = structlog.get_logger()

HEADERS = {
    "Authorization": f"Bearer {settings.sprinthub_api_key}",
    "Content-Type": "application/json",
}

# Mapeamento de estágio interno → coluna do pipeline no SprintHub
STAGE_TO_COLUMN: dict[LeadStage, str] = {
    LeadStage.NEW: "Novo Lead",
    LeadStage.IDENTIFYING: "Em Qualificação",
    LeadStage.NURTURING: "Em Nutrição",
    LeadStage.OBJECTION: "Com Objeção",
    LeadStage.HOT: "Lead Quente",
    LeadStage.NEGOTIATING: "Em Negociação",
    LeadStage.CONVERTED: "Convertido",
    LeadStage.ESCALATED: "Aguardando Humano",
    LeadStage.LOST: "Perdido",
}

# Pipeline por curso
PIPELINE_BY_COURSE = {
    "curso_1": settings.sprinthub_pipeline_curso_1,
    "curso_2": settings.sprinthub_pipeline_curso_2,
}


async def create_lead(lead: Lead) -> Optional[str]:
    """
    Cria um card de lead no SprintHub.
    Retorna o ID do card criado.
    """
    pipeline_id = PIPELINE_BY_COURSE.get(lead.course_slug.value, "")
    if not pipeline_id:
        logger.warning("Pipeline não configurado para o curso.", course=lead.course_slug)

    payload = {
        "name": lead.name or lead.phone_number,
        "phone": lead.phone_number,
        "pipeline_id": pipeline_id,
        "stage": STAGE_TO_COLUMN.get(lead.stage, "Novo Lead"),
        "source": "WhatsApp",
        "custom_fields": {
            "curso_interesse": lead.course_slug.value,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.sprinthub_api_url}/leads",
                json=payload,
                headers=HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
            sprinthub_id = str(data.get("id", ""))
            logger.info("✅ Lead criado no SprintHub.", id=sprinthub_id, phone=lead.phone_number)
            return sprinthub_id
    except httpx.HTTPError as e:
        logger.error("❌ Erro ao criar lead no SprintHub.", error=str(e))
        return None


async def update_lead_stage(lead: Lead) -> bool:
    """
    Atualiza o estágio (coluna do kanban) de um lead existente no SprintHub.
    """
    if not lead.sprinthub_id:
        logger.warning("Lead sem sprinthub_id, não é possível atualizar.", phone=lead.phone_number)
        return False

    payload = {
        "stage": STAGE_TO_COLUMN.get(lead.stage, "Em Qualificação"),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.patch(
                f"{settings.sprinthub_api_url}/leads/{lead.sprinthub_id}",
                json=payload,
                headers=HEADERS,
            )
            resp.raise_for_status()
            logger.info(
                "🔄 Lead atualizado no SprintHub.",
                id=lead.sprinthub_id,
                stage=lead.stage.value,
            )
            return True
    except httpx.HTTPError as e:
        logger.error("❌ Erro ao atualizar lead no SprintHub.", error=str(e))
        return False


async def add_note(lead: Lead, note: str) -> bool:
    """
    Adiciona uma nota/comentário no card do lead no SprintHub.
    """
    if not lead.sprinthub_id:
        return False

    payload = {"content": note}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.sprinthub_api_url}/leads/{lead.sprinthub_id}/notes",
                json=payload,
                headers=HEADERS,
            )
            resp.raise_for_status()
            return True
    except httpx.HTTPError as e:
        logger.error("❌ Erro ao adicionar nota no SprintHub.", error=str(e))
        return False


async def sync_lead(lead: Lead) -> Lead:
    """
    Sincroniza o lead com o SprintHub:
    - Cria se não existir (sem sprinthub_id)
    - Atualiza o estágio se já existir
    Retorna o lead atualizado com o sprinthub_id.
    """
    if not lead.sprinthub_id:
        sprinthub_id = await create_lead(lead)
        if sprinthub_id:
            lead = lead.model_copy(update={"sprinthub_id": sprinthub_id})
    else:
        await update_lead_stage(lead)

    return lead
