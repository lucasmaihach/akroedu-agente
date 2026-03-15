import anthropic
import structlog

from app.config import settings
from app.models.lead import Lead, CourseSlug
from app.memory.session import get_history, update_lead_field

logger = structlog.get_logger()

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# Lista de cursos disponíveis para o router conhecer
COURSES_DESCRIPTION = """
- curso_1: [NOME DO CURSO 1] — [breve descrição do curso 1]
- curso_2: [NOME DO CURSO 2] — [breve descrição do curso 2]
- pos_fisio_neuro: Pós-Graduação em Fisioterapia Neurofuncional — para fisioterapeutas que querem se especializar em neurorreabilitação (adulto, pediátrico e home care)
"""

ROUTER_SYSTEM_PROMPT = f"""
Você é um classificador silencioso de intenção de leads.
Sua única tarefa é identificar qual curso de pós-graduação o lead tem interesse,
com base na conversa fornecida.

Cursos disponíveis:
{COURSES_DESCRIPTION}

Responda APENAS com um dos valores abaixo (sem explicação, sem pontuação):
- curso_1
- curso_2
- pos_fisio_neuro
- unknown

Regras:
- Se o lead mencionou explicitamente o nome ou área do curso 1, retorne: curso_1
- Se o lead mencionou explicitamente o nome ou área do curso 2, retorne: curso_2
- Se o lead mencionou fisioterapia, neurologia, fisio neuro, neurofuncional ou reabilitação neurológica, retorne: pos_fisio_neuro
- Se não for possível determinar, retorne: unknown
"""


async def identify_course(lead: Lead, user_message: str) -> CourseSlug:
    """
    Usa o Claude para identificar qual curso o lead está interessado
    com base na mensagem atual e no histórico da conversa.
    Atualiza o course_slug do lead se identificado.
    """
    # Se já identificamos o curso, não precisa rodar o router novamente
    if lead.course_slug != CourseSlug.UNKNOWN:
        return lead.course_slug

    history = await get_history(lead.phone_number, last_n=10)

    # Monta histórico + mensagem atual para análise
    messages_for_router = history + [{"role": "user", "content": user_message}]

    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=10,
            system=ROUTER_SYSTEM_PROMPT,
            messages=messages_for_router,
        )
        raw = response.content[0].text.strip().lower()

        if raw in [c.value for c in CourseSlug]:
            course = CourseSlug(raw)
        else:
            course = CourseSlug.UNKNOWN

    except Exception as e:
        logger.error("❌ Erro no router agent.", error=str(e))
        course = CourseSlug.UNKNOWN

    # Atualiza o lead se identificou o curso
    if course != CourseSlug.UNKNOWN:
        await update_lead_field(lead.phone_number, course_slug=course)
        logger.info("🔀 Curso identificado pelo router.", phone=lead.phone_number, course=course)

    return course
