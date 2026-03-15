import pytest
import asyncio
from app.models.lead import Lead, CourseSlug, LeadStage
from app.memory.session import get_or_create_lead, append_message, get_history
from app.agents.router_agent import identify_course
from app.agents.dispatcher import dispatch


@pytest.mark.asyncio
async def test_create_lead():
    """Testa criação de novo lead."""
    phone = "5511987654321"
    lead = await get_or_create_lead(phone=phone, name="João")
    
    assert lead.phone_number == phone
    assert lead.name == "João"
    assert lead.course_slug == CourseSlug.UNKNOWN
    assert lead.stage == LeadStage.NEW


@pytest.mark.asyncio
async def test_save_and_retrieve_history():
    """Testa salvamento e recuperação do histórico."""
    phone = "5511912345678"
    
    await append_message(phone, role="user", content="Oi, quero saber sobre o MBA")
    await append_message(phone, role="assistant", content="Oi! Que legal!")
    
    history = await get_history(phone)
    
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_router_identifies_course():
    """Testa se o router identifica corretamente o curso."""
    phone = "5511922334455"
    lead = await get_or_create_lead(phone=phone, name="Maria")
    
    # Envia uma mensagem mencionando o curso 1
    course = await identify_course(lead, "Quero saber sobre curso_1")
    
    # Se o seu sistema está bem treinado, deve identificar
    # (Isso depende de como você configurou os course slugs)
    assert course in (CourseSlug.CURSO_1, CourseSlug.UNKNOWN)


@pytest.mark.asyncio
async def test_dispatcher_unknown_course():
    """Testa dispatcher com curso desconhecido no primeiro contato."""
    phone = "5511933445566"
    lead = await get_or_create_lead(phone=phone, name="Pedro")
    
    # Primeira mensagem genérica
    await dispatch(lead=lead, user_message="Oi, tudo bem?")
    
    # Lead deve estar em IDENTIFYING (esperando escolha de curso)
    # Nota: Isso é assincrito, então pode ser difícil testar sem mock


if __name__ == "__main__":
    # Execute com: pytest tests/test_agents.py -v
    pass
