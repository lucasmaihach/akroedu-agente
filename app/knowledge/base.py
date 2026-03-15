from pathlib import Path
from functools import lru_cache
import structlog

logger = structlog.get_logger()

KNOWLEDGE_DIR = Path(__file__).parent / "courses"


@lru_cache(maxsize=10)
def load_knowledge(course_slug: str) -> str:
    """
    Carrega o arquivo .md com as informações do curso.
    O resultado é cacheado em memória para evitar I/O repetido.
    """
    path = KNOWLEDGE_DIR / f"{course_slug}.md"

    if not path.exists():
        logger.warning("Knowledge base não encontrada.", course=course_slug, path=str(path))
        return f"Informações sobre o curso '{course_slug}' não disponíveis no momento."

    content = path.read_text(encoding="utf-8")
    logger.info("📚 Knowledge base carregada.", course=course_slug, chars=len(content))
    return content


def reload_knowledge(course_slug: str) -> str:
    """Força o recarregamento da knowledge base (útil após editar os .md)."""
    load_knowledge.cache_clear()
    return load_knowledge(course_slug)
