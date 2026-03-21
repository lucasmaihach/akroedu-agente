import anthropic
import structlog
import unicodedata

from app.config import settings
from app.models.lead import Lead, CourseSlug
from app.memory.session import get_history, update_lead_field
from app.services.error_alert import notify_conversation_error

logger = structlog.get_logger()

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower().strip())
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return " ".join(normalized.split())


def _deterministic_course_match(user_message: str) -> CourseSlug:
    """
    Fallback determinístico para casos óbvios antes de chamar o LLM.
    Ex.: mensagens com "fisioterapia" + "neuro/neurofuncional".
    """
    text = _normalize_text(user_message)

    fisio_terms = ("fisioterapia", "fisio", "fisioterapeuta")
    neuro_terms = ("neuro", "neurofuncional", "neurorreabilitacao", "reabilitacao neurologica")

    if any(term in text for term in fisio_terms) and any(term in text for term in neuro_terms):
        return CourseSlug.POS_FISIO_NEURO

    # Quando mencionar apenas fisioterapia, priorizamos o curso de fisio/neuro.
    # Evita cair em "unknown" para entradas curtas como "fisioterapia".
    if any(term in text for term in fisio_terms):
        return CourseSlug.POS_FISIO_NEURO

    return CourseSlug.UNKNOWN


def _build_router_prompt() -> str:
    """
    Monta o system prompt do router dinamicamente a partir dos configs de cada script.
    Para adicionar um novo produto, basta registrá-lo em engine.SCRIPT_CONFIGS
    com os campos 'name' e 'keywords' — o router passa a reconhecê-lo automaticamente.
    """
    from app.script.engine import SCRIPT_CONFIGS

    lines = []
    valid_slugs = []
    keyword_rules = []

    for slug, config in SCRIPT_CONFIGS.items():
        name = config.get("name", slug.value)
        keywords = config.get("keywords", [])
        lines.append(f"- {slug.value}: {name}")
        valid_slugs.append(slug.value)
        if keywords:
            kw_str = ", ".join(keywords)
            keyword_rules.append(
                f"- Se o lead mencionou {kw_str}, retorne: {slug.value}"
            )

    courses_block = "\n".join(lines)
    valid_block = "\n".join(f"- {s}" for s in valid_slugs) + "\n- unknown"
    rules_block = "\n".join(keyword_rules) if keyword_rules else "- Use o contexto da conversa para identificar o curso."

    return f"""
Você é um classificador silencioso de intenção de leads.
Sua única tarefa é identificar qual curso de pós-graduação o lead tem interesse,
com base na conversa fornecida.

Cursos disponíveis:
{courses_block}

Responda APENAS com um dos valores abaixo (sem explicação, sem pontuação):
{valid_block}

Regras:
{rules_block}
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

    deterministic = _deterministic_course_match(user_message)
    if deterministic != CourseSlug.UNKNOWN:
        await update_lead_field(lead.phone_number, course_slug=deterministic)
        logger.info("🔀 Curso identificado por fallback determinístico.", phone=lead.phone_number, course=deterministic)
        return deterministic

    history = await get_history(lead.phone_number, last_n=10)

    # Monta histórico + mensagem atual para análise
    messages_for_router = history + [{"role": "user", "content": user_message}]

    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=10,
            system=_build_router_prompt(),
            messages=messages_for_router,
        )
        raw = response.content[0].text.strip().lower().replace(" ", "_")

        if raw in [c.value for c in CourseSlug]:
            course = CourseSlug(raw)
        else:
            course = CourseSlug.UNKNOWN

    except Exception as e:
        logger.error("❌ Erro no router agent.", error=str(e))
        await notify_conversation_error(
            source="anthropic.router",
            error=e,
            phone=lead.phone_number,
            lead_name=lead.name,
            stage=lead.stage.value,
            user_message=user_message,
            extra={"history_size": len(history)},
        )
        course = CourseSlug.UNKNOWN

    # Atualiza o lead se identificou o curso
    if course != CourseSlug.UNKNOWN:
        await update_lead_field(lead.phone_number, course_slug=course)
        logger.info("🔀 Curso identificado pelo router.", phone=lead.phone_number, course=course)

    return course
