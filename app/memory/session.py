import json
import redis.asyncio as aioredis
import structlog
from typing import Optional, AsyncIterator

from datetime import datetime, timezone
import uuid

from app.config import settings
from app.models.lead import Lead, LeadStage, CourseSlug

logger = structlog.get_logger()

_redis: Optional[aioredis.Redis] = None


async def init_redis():
    """Inicializa o pool de conexão com o Redis."""
    global _redis
    _redis = await aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    await _redis.ping()
    logger.info("✅ Redis conectado.", url=settings.redis_url)


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis não foi inicializado. Chame init_redis() primeiro.")
    return _redis


# ── Chaves Redis ──────────────────────────────────────────────────────────────

def _lead_key(phone: str) -> str:
    return f"lead:{phone}"


def _history_key(phone: str) -> str:
    return f"history:{phone}"


def _script_lock_key(phone: str) -> str:
    """Lock para evitar duplo disparo do script de áudio."""
    return f"script_lock:{phone}"


def _followup_lock_key(phone: str) -> str:
    """Lock para evitar processamento duplicado de follow-up no mesmo lead."""
    return f"followup_lock:{phone}"


# ── Gerenciamento do Lead em cache ────────────────────────────────────────────

async def get_lead(phone: str) -> Optional[Lead]:
    """Recupera o lead do Redis. Retorna None se não existir."""
    r = get_redis()
    data = await r.get(_lead_key(phone))
    if data:
        return Lead(**json.loads(data))
    return None


async def save_lead(lead: Lead) -> None:
    """Salva ou atualiza o lead no Redis com TTL."""
    r = get_redis()
    ttl = settings.session_ttl_hours * 3600
    await r.set(
        _lead_key(lead.phone_number),
        lead.model_dump_json(),
        ex=ttl,
    )


async def get_or_create_lead(phone: str, name: Optional[str] = None) -> Lead:
    """Retorna o lead existente ou cria um novo."""
    lead = await get_lead(phone)
    if lead is None:
        lead = Lead(
            phone_number=phone,
            name=name,
            stage=LeadStage.NEW,
            course_slug=CourseSlug.UNKNOWN,
            script_step=0,
        )
        await save_lead(lead)
        logger.info("🆕 Novo lead criado.", phone=phone, name=name)
    return lead


async def update_lead_field(phone: str, **kwargs) -> Lead:
    """Atualiza campos específicos do lead no Redis."""
    lead = await get_lead(phone)
    if lead is None:
        raise ValueError(f"Lead {phone} não encontrado no Redis.")
    updated = lead.model_copy(update=kwargs)
    await save_lead(updated)
    return updated


# ── Histórico de conversa ─────────────────────────────────────────────────────

async def append_message(phone: str, role: str, content: str) -> None:
    """Adiciona uma mensagem ao histórico da conversa (lista no Redis)."""
    r = get_redis()
    message = json.dumps({"role": role, "content": content})
    ttl = settings.session_ttl_hours * 3600
    key = _history_key(phone)
    await r.rpush(key, message)
    await r.expire(key, ttl)


async def get_history(phone: str, last_n: int = 20) -> list[dict]:
    """Retorna as últimas N mensagens do histórico."""
    r = get_redis()
    raw_messages = await r.lrange(_history_key(phone), -last_n, -1)
    return [json.loads(m) for m in raw_messages]


async def clear_history(phone: str) -> None:
    """Limpa o histórico da conversa (usado em testes ou reset)."""
    r = get_redis()
    await r.delete(_history_key(phone))


# ── Script lock ───────────────────────────────────────────────────────────────

async def set_script_lock(phone: str, ttl_seconds: int = 60) -> bool:
    """
    Tenta adquirir o lock para o próximo passo do script.
    Retorna True se adquiriu, False se já estava locked.
    Evita que dois workers disparem o mesmo áudio simultaneamente.
    """
    r = get_redis()
    result = await r.set(_script_lock_key(phone), "1", nx=True, ex=ttl_seconds)
    return result is True


async def release_script_lock(phone: str) -> None:
    r = get_redis()
    await r.delete(_script_lock_key(phone))


# ── Cache de media_id de áudios (evita re-upload) ────────────────────────────

async def get_cached_media_id(filename: str) -> Optional[str]:
    """Retorna o media_id em cache para um arquivo de áudio, ou None se não existir."""
    r = get_redis()
    val = await r.get(f"media_id:{filename}")
    return val if val else None


async def cache_media_id(filename: str, media_id: str) -> None:
    """Armazena o media_id de um áudio no Redis por 25 dias (limite Meta: 30 dias)."""
    r = get_redis()
    await r.set(f"media_id:{filename}", media_id, ex=60 * 60 * 24 * 25)


# ── Deduplicação de mensagens da Meta ─────────────────────────────────────────

def _msg_seen_key(message_id: str) -> str:
    return f"msg_seen:{message_id}"


async def is_message_already_processed(message_id: str) -> bool:
    """
    Verifica se uma mensagem já foi processada (evita duplo disparo da Meta).
    Marca como processada com TTL de 5 minutos.
    """
    r = get_redis()
    key = _msg_seen_key(message_id)
    # SETNX: só define se NÃO existir. Retorna True se acabou de criar (novo),
    # False se já existia (duplicata).
    result = await r.set(key, "1", nx=True, ex=300)  # TTL: 5 minutos
    return result is None  # None = chave já existia = mensagem duplicada


async def iter_leads() -> AsyncIterator[Lead]:
    """Itera por todos os leads armazenados no Redis."""
    r = get_redis()
    async for key in r.scan_iter(match="lead:*"):
        data = await r.get(key)
        if not data:
            continue
        try:
            yield Lead(**json.loads(data))
        except Exception as e:
            logger.warning("Lead inválido no Redis, ignorando.", key=key, error=str(e))


async def acquire_followup_lock(phone: str, ttl_seconds: int = 30) -> Optional[str]:
    """Adquire lock de follow-up e retorna token único. None se lock já existir."""
    r = get_redis()
    token = f"{datetime.now(timezone.utc).timestamp()}:{uuid.uuid4().hex}"
    ok = await r.set(_followup_lock_key(phone), token, nx=True, ex=ttl_seconds)
    return token if ok else None


async def release_followup_lock(phone: str, token: str) -> None:
    """Libera lock de follow-up apenas se o token bater."""
    r = get_redis()
    key = _followup_lock_key(phone)
    current = await r.get(key)
    if current == token:
        await r.delete(key)
