import pytest

from app.agents.dispatcher import dispatch
from app.memory.session import append_message, get_history, get_lead, get_or_create_lead, save_lead
from app.models.lead import CourseSlug, Lead, LeadStage
from app.script.engine import run_script_step


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
async def test_dispatch_unknown_course_moves_to_identifying(monkeypatch):
    """Quando não identifica curso no primeiro contato, dispatcher deve pedir qualificação."""
    phone = "5511933445566"
    lead = await get_or_create_lead(phone=phone, name="Pedro")
    sent_messages: list[str] = []

    async def fake_identify_course(*_args, **_kwargs):
        return CourseSlug.UNKNOWN

    async def fake_send_text(*_args, **kwargs):
        sent_messages.append(kwargs["text"])
        return {"status": "ok"}

    monkeypatch.setattr("app.agents.dispatcher.identify_course", fake_identify_course)
    monkeypatch.setattr("app.agents.dispatcher.whatsapp.send_text", fake_send_text)
    monkeypatch.setattr("app.agents.dispatcher.is_within_business_hours", lambda *_args, **_kwargs: True)

    should_advance = await dispatch(lead=lead, user_message="Oi, tudo bem?")
    updated = await get_lead(phone)

    assert should_advance is False
    assert updated is not None
    assert updated.stage == LeadStage.IDENTIFYING
    assert len(sent_messages) == 1
    assert "qual dos nossos cursos" in sent_messages[0].lower()


@pytest.mark.asyncio
async def test_dispatch_identified_course_moves_to_nurturing(monkeypatch):
    """Quando identifica curso no primeiro contato, dispatcher deve iniciar nurturing/script."""
    phone = "5511944455566"
    lead = await get_or_create_lead(phone=phone, name="Maria")

    async def fake_identify_course(*_args, **_kwargs):
        return CourseSlug.CURSO_1

    monkeypatch.setattr("app.agents.dispatcher.identify_course", fake_identify_course)

    should_advance = await dispatch(lead=lead, user_message="Quero saber sobre gestão de projetos")
    updated = await get_lead(phone)

    assert should_advance is True
    assert updated is not None
    assert updated.stage == LeadStage.NURTURING
    assert updated.course_slug == CourseSlug.CURSO_1


@pytest.mark.asyncio
async def test_run_script_step_sends_content_and_advances(monkeypatch):
    """Garante execução de passo do script sem chamadas externas."""
    phone = "5511955566677"
    lead = Lead(
        phone_number=phone,
        name="Teste",
        course_slug=CourseSlug.CURSO_1,
        stage=LeadStage.NURTURING,
        script_step=0,
        last_received_msg_id="wamid_test",
    )
    await save_lead(lead)

    sent_texts: list[str] = []
    sent_audios: list[str] = []

    async def fake_sleep(*_args, **_kwargs):
        return None

    async def fake_typing(*_args, **_kwargs):
        return None

    async def fake_send_text(*_args, **kwargs):
        sent_texts.append(kwargs["text"])
        return {"status": "ok"}

    async def fake_send_audio(*_args, **kwargs):
        sent_audios.append(kwargs["media_id"])
        return {"status": "ok"}

    monkeypatch.setattr("app.script.engine.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.script.engine.whatsapp.send_typing_and_wait", fake_typing)
    monkeypatch.setattr("app.script.engine.whatsapp.send_text", fake_send_text)
    monkeypatch.setattr("app.script.engine.whatsapp.send_audio_by_media_id", fake_send_audio)

    sent = await run_script_step(phone)
    updated = await get_lead(phone)

    assert sent is True
    assert updated is not None
    assert updated.script_step == 1
    assert len(sent_texts) >= 2
    assert len(sent_audios) == 1
