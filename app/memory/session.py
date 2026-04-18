import json
import redis.asyncio as aioredis
import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import Optional, AsyncIterator

from datetime import datetime, timezone
import uuid

from app.config import settings
from app.models.lead import Lead, LeadStage, CourseSlug
from app.db.database import AsyncSessionLocal
from app.db.orm_models import LeadORM
from app.utils.gender_detection import detect_gender_from_name
from app.utils.phone import normalize_phone, phone_variants, is_canonical_br_phone

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


def _context_reply_count_key(phone: str, step: int) -> str:
    """Contador de respostas contextuais por lead/step do script."""
    return f"context_reply_count:{phone}:step:{step}"


def _ops_alert_cooldown_key(phone: str, alert_key: str) -> str:
    """Cooldown curto para não repetir o mesmo alerta interno em loop."""
    return f"ops_alert_cd:{phone}:{alert_key}"


# ── Gerenciamento do Lead em cache ────────────────────────────────────────────

def _to_db_datetime(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _lead_from_orm(lead_orm: LeadORM) -> Lead:
    """Converte registro do PostgreSQL para o modelo de domínio Lead."""
    try:
        course_slug = CourseSlug(lead_orm.course_slug)
    except ValueError:
        course_slug = CourseSlug.UNKNOWN

    try:
        stage = LeadStage(lead_orm.stage)
    except ValueError:
        stage = LeadStage.NEW

    return Lead(
        phone_number=lead_orm.phone_number,
        name=lead_orm.name,
        gender=lead_orm.gender,
        course_slug=course_slug,
        stage=stage,
        sprinthub_id=lead_orm.sprinthub_id,
        twenty_person_id=lead_orm.twenty_person_id,
        twenty_opportunity_id=lead_orm.twenty_opportunity_id,
        chatwoot_contact_id=lead_orm.chatwoot_contact_id,
        chatwoot_conversation_id=lead_orm.chatwoot_conversation_id,
        chatwoot_chat_url=lead_orm.chatwoot_chat_url,
        script_step=lead_orm.script_step,
        is_escalated=lead_orm.is_escalated,
        price_ask_count=lead_orm.price_ask_count,
        last_received_msg_id=lead_orm.last_received_msg_id,
        notes=lead_orm.notes,
        followup_enabled=lead_orm.followup_enabled,
        followup_status=lead_orm.followup_status,
        followup_scenario=lead_orm.followup_scenario,
        followup_step=lead_orm.followup_step,
        followup_next_at=lead_orm.followup_next_at,
        followup_anchor_at=lead_orm.followup_anchor_at,
        followup_started_at=lead_orm.followup_started_at,
        followup_finished_at=lead_orm.followup_finished_at,
        followup_stopped_reason=lead_orm.followup_stopped_reason,
        last_inbound_at=lead_orm.last_inbound_at,
        price_sent_at=lead_orm.price_sent_at,
        last_unknown_prompt_at=lead_orm.last_unknown_prompt_at,
        awaiting_template_reply=lead_orm.awaiting_template_reply,
        pending_welcome_template=lead_orm.pending_welcome_template,
        welcome_template_name=lead_orm.welcome_template_name,
        welcome_next_at=lead_orm.welcome_next_at,
        agent_paused=lead_orm.agent_paused,
        last_script_block=lead_orm.last_script_block,
    )


async def _get_lead_postgres(phone: str) -> Optional[Lead]:
    """Busca estado persistido do lead no PostgreSQL."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(LeadORM).where(LeadORM.phone_number == phone)
            result = await session.execute(stmt)
            lead_orm = result.scalar_one_or_none()
            if not lead_orm:
                return None
            return _lead_from_orm(lead_orm)
    except Exception as e:
        logger.error("❌ Falha ao buscar lead no PostgreSQL.", phone=phone, error=str(e))
        return None


async def _save_lead_postgres(lead: Lead) -> None:
    """Persiste estado completo do lead no PostgreSQL (fallback durável)."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(LeadORM).where(LeadORM.phone_number == lead.phone_number)
            result = await session.execute(stmt)
            lead_orm = result.scalar_one_or_none()

            if lead_orm is None:
                lead_orm = LeadORM(phone_number=lead.phone_number)
                session.add(lead_orm)

            lead_orm.name = lead.name
            lead_orm.gender = lead.gender
            lead_orm.course_slug = lead.course_slug.value
            lead_orm.stage = lead.stage.value
            lead_orm.sprinthub_id = lead.sprinthub_id
            lead_orm.twenty_person_id = lead.twenty_person_id
            lead_orm.twenty_opportunity_id = lead.twenty_opportunity_id
            lead_orm.chatwoot_contact_id = lead.chatwoot_contact_id
            lead_orm.chatwoot_conversation_id = lead.chatwoot_conversation_id
            lead_orm.chatwoot_chat_url = lead.chatwoot_chat_url
            lead_orm.script_step = lead.script_step
            lead_orm.is_escalated = lead.is_escalated
            lead_orm.price_ask_count = lead.price_ask_count
            lead_orm.last_received_msg_id = lead.last_received_msg_id
            lead_orm.notes = lead.notes

            lead_orm.followup_enabled = lead.followup_enabled
            lead_orm.followup_status = lead.followup_status
            lead_orm.followup_scenario = lead.followup_scenario
            lead_orm.followup_step = lead.followup_step
            lead_orm.followup_next_at = _to_db_datetime(lead.followup_next_at)
            lead_orm.followup_anchor_at = _to_db_datetime(lead.followup_anchor_at)
            lead_orm.followup_started_at = _to_db_datetime(lead.followup_started_at)
            lead_orm.followup_finished_at = _to_db_datetime(lead.followup_finished_at)
            lead_orm.followup_stopped_reason = lead.followup_stopped_reason

            lead_orm.last_inbound_at = _to_db_datetime(lead.last_inbound_at)
            lead_orm.price_sent_at = _to_db_datetime(lead.price_sent_at)
            lead_orm.last_unknown_prompt_at = _to_db_datetime(lead.last_unknown_prompt_at)

            lead_orm.awaiting_template_reply = lead.awaiting_template_reply
            lead_orm.pending_welcome_template = lead.pending_welcome_template
            lead_orm.welcome_template_name = lead.welcome_template_name
            lead_orm.welcome_next_at = _to_db_datetime(lead.welcome_next_at)
            lead_orm.agent_paused = lead.agent_paused
            lead_orm.last_script_block = lead.last_script_block

            await session.commit()
    except Exception as e:
        logger.error("❌ Falha ao persistir lead no PostgreSQL.", phone=lead.phone_number, error=str(e))
        # Fail-fast: sem persistência durável, o estado do lead pode quebrar follow-up/debounce.
        raise


async def get_lead(phone: str) -> Optional[Lead]:
    """Recupera o lead do Redis e, se necessário, do PostgreSQL."""
    phone = normalize_phone(phone)
    r = get_redis()
    data = await r.get(_lead_key(phone))
    if data:
        return Lead(**json.loads(data))

    lead = await _get_lead_postgres(phone)
    if lead:
        await save_lead(lead)
    return lead


async def save_lead(lead: Lead) -> None:
    """Salva ou atualiza o lead no Redis e no PostgreSQL."""
    lead = lead.model_copy(update={"phone_number": normalize_phone(lead.phone_number)})
    r = get_redis()
    ttl = settings.session_ttl_hours * 3600
    await r.set(
        _lead_key(lead.phone_number),
        lead.model_dump_json(),
        ex=ttl,
    )
    await _save_lead_postgres(lead)


async def get_or_create_lead(phone: str, name: Optional[str] = None) -> Lead:
    """Retorna o lead existente ou cria um novo."""
    phone = normalize_phone(phone)
    lead = await get_lead(phone)
    if lead is None:
        gender = detect_gender_from_name(name) if name else "male"
        lead = Lead(
            phone_number=phone,
            name=name,
            gender=gender,
            stage=LeadStage.NEW,
            course_slug=CourseSlug.UNKNOWN,
            script_step=0,
        )
        await save_lead(lead)
        logger.info("🆕 Novo lead criado.", phone=phone, name=name, gender=gender)
    elif lead.name != name and name is not None:
        # Se o nome foi corrigido, atualiza gênero também
        lead.name = name
        lead.gender = detect_gender_from_name(name)
        await save_lead(lead)
    return lead


async def update_lead_field(phone: str, **kwargs) -> Lead:
    """Atualiza campos específicos do lead no Redis."""
    phone = normalize_phone(phone)
    lead = await get_lead(phone)
    if lead is None:
        raise ValueError(f"Lead {phone} não encontrado no Redis.")
    updated = lead.model_copy(update=kwargs)
    await save_lead(updated)
    return updated


# ── Histórico de conversa ─────────────────────────────────────────────────────

async def append_message(phone: str, role: str, content: str) -> None:
    """Adiciona mensagem no Redis (cache) e também persiste no PostgreSQL."""
    phone = normalize_phone(phone)
    # Cache temporário no Redis (usado pelo agente em tempo real)
    r = get_redis()
    message = json.dumps({"role": role, "content": content})
    ttl = settings.session_ttl_hours * 3600
    key = _history_key(phone)
    await r.rpush(key, message)
    await r.expire(key, ttl)

    # Persistência definitiva no PostgreSQL (para relatórios e auditoria)
    try:
        from app.db.database import AsyncSessionLocal
        from app.db.orm_models import ConversationORM

        async with AsyncSessionLocal() as session:
            session.add(
                ConversationORM(
                    phone_number=phone,
                    role=role,
                    content=content,
                )
            )
            await session.commit()
    except Exception as e:
        logger.error(
            "❌ Falha ao persistir conversa no PostgreSQL.",
            phone=phone,
            role=role,
            error=str(e),
        )


async def get_history(phone: str, last_n: int = 20) -> list[dict]:
    """Retorna as últimas N mensagens do histórico em cache (Redis)."""
    r = get_redis()
    raw_messages = await r.lrange(_history_key(phone), -last_n, -1)
    return [json.loads(m) for m in raw_messages]


async def get_history_persistent(phone: str, last_n: int = 200) -> list[dict]:
    """Retorna histórico persistido no PostgreSQL (não expira com TTL)."""
    try:
        from app.db.database import AsyncSessionLocal
        from app.db.orm_models import ConversationORM

        async with AsyncSessionLocal() as session:
            stmt = (
                select(ConversationORM)
                .where(ConversationORM.phone_number == phone)
                .order_by(ConversationORM.created_at.desc())
                .limit(last_n)
            )
            result = await session.execute(stmt)
            rows = list(result.scalars().all())

        rows.reverse()  # mais antigo -> mais novo
        return [
            {
                "role": row.role,
                "content": row.content,
                "timestamp": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(
            "❌ Falha ao buscar histórico persistente no PostgreSQL.",
            phone=phone,
            error=str(e),
        )
        return []


async def clear_history(phone: str) -> None:
    """Limpa o histórico da conversa (usado em testes ou reset)."""
    phone = normalize_phone(phone)
    r = get_redis()
    await r.delete(_history_key(phone))


async def get_context_reply_count(phone: str, step: int) -> int:
    phone = normalize_phone(phone)
    r = get_redis()
    raw = await r.get(_context_reply_count_key(phone, step))
    try:
        return int(raw or 0)
    except Exception:
        return 0


async def increment_context_reply_count(phone: str, step: int) -> int:
    """
    Incrementa contador de respostas contextuais para o step atual.
    TTL acompanha TTL da sessão.
    """
    phone = normalize_phone(phone)
    r = get_redis()
    key = _context_reply_count_key(phone, step)
    value = await r.incr(key)
    ttl = settings.session_ttl_hours * 3600
    await r.expire(key, ttl)
    return int(value)


async def acquire_ops_alert_cooldown(phone: str, alert_key: str, ttl_seconds: int = 30 * 60) -> bool:
    """
    Evita spam de alertas internos repetidos para o mesmo lead/contexto.
    Retorna True quando o alerta deve ser enviado.
    """
    phone = normalize_phone(phone)
    r = get_redis()
    normalized_alert_key = (alert_key or "default").strip().lower().replace(" ", "_")
    return bool(await r.set(_ops_alert_cooldown_key(phone, normalized_alert_key), "1", nx=True, ex=ttl_seconds))


async def resolve_lead_phone(phone: str) -> str:
    """
    Resolve a identidade do lead por variações equivalentes do telefone.
    Evita split de conversa entre versões com/sem 9º dígito.
    """
    canonical = normalize_phone(phone)
    if not canonical:
        return canonical

    direct = await get_lead(canonical)
    if direct is not None:
        return direct.phone_number

    for variant in phone_variants(canonical):
        if variant == canonical:
            continue
        found = await get_lead(variant)
        if found is not None:
            return found.phone_number

    resolved_by_suffix = await _resolve_lead_phone_by_suffix(canonical)
    if resolved_by_suffix:
        return resolved_by_suffix

    return canonical


async def _resolve_lead_phone_by_suffix(phone: str) -> str | None:
    """
    Fallback para números malformados:
    tenta vincular por sufixo quando existir UM único lead candidato.
    """
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    if is_canonical_br_phone(normalized):
        return None

    try:
        async with AsyncSessionLocal() as session:
            for tail_size in (11, 10, 9, 8):
                if len(normalized) < tail_size:
                    continue
                tail = normalized[-tail_size:]
                stmt = (
                    select(LeadORM.phone_number)
                    .where(LeadORM.phone_number.like(f"%{tail}"))
                    .limit(3)
                )
                rows = (await session.execute(stmt)).scalars().all()
                unique = list(dict.fromkeys(rows))
                if len(unique) == 1:
                    logger.warning(
                        "Telefone inbound malformado resolvido por fallback de sufixo.",
                        raw=phone,
                        normalized=normalized,
                        resolved=unique[0],
                        tail_size=tail_size,
                    )
                    return unique[0]
    except Exception as e:
        logger.warning(
            "Falha no fallback de resolução por sufixo.",
            phone=phone,
            normalized=normalized,
            error=str(e),
        )

    return None


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

MSG_DEDUP_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 dias


def _msg_seen_key(message_id: str) -> str:
    return f"msg_seen:{message_id}"


async def _is_message_already_processed_postgres(message_id: str) -> bool:
    """Deduplicação forte em persistência (PostgreSQL)."""
    from app.db.database import AsyncSessionLocal
    from app.db.orm_models import ProcessedMessageORM

    async with AsyncSessionLocal() as session:
        try:
            session.add(ProcessedMessageORM(message_id=message_id))
            await session.commit()
            return False
        except IntegrityError:
            await session.rollback()
            return True
        except Exception as e:
            await session.rollback()
            logger.warning(
                "Falha na deduplicação persistente do message_id.",
                message_id=message_id,
                error=str(e),
            )
            return False


async def is_message_already_processed(message_id: str) -> bool:
    """
    Verifica se uma mensagem já foi processada (evita reprocessamento por reentrega da Meta).

    Estratégia em 2 camadas:
    1) Redis (rápido, TTL longo de 30 dias)
    2) PostgreSQL (persistente, sobrevive a restart/flush de Redis)
    """
    r = get_redis()
    key = _msg_seen_key(message_id)

    cached = await r.set(key, "1", nx=True, ex=MSG_DEDUP_TTL_SECONDS)
    if cached is None:
        return True

    already_in_db = await _is_message_already_processed_postgres(message_id)
    if already_in_db:
        await r.set(key, "1", ex=MSG_DEDUP_TTL_SECONDS)
        return True

    return False


async def _iter_leads_postgres() -> AsyncIterator[Lead]:
    """Itera por todos os leads persistidos no PostgreSQL."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(LeadORM))
            for row in result.scalars().all():
                try:
                    yield _lead_from_orm(row)
                except Exception as e:
                    logger.warning("Lead inválido no PostgreSQL, ignorando.", phone=row.phone_number, error=str(e))
    except Exception as e:
        logger.error("❌ Falha ao iterar leads no PostgreSQL.", error=str(e))


async def iter_leads() -> AsyncIterator[Lead]:
    """Itera por todos os leads disponíveis em Redis e PostgreSQL, sem duplicar."""
    yielded: set[str] = set()

    r = get_redis()
    async for key in r.scan_iter(match="lead:*"):
        data = await r.get(key)
        if not data:
            continue
        try:
            lead = Lead(**json.loads(data))
            yielded.add(lead.phone_number)
            yield lead
        except Exception as e:
            logger.warning("Lead inválido no Redis, ignorando.", key=key, error=str(e))

    async for lead in _iter_leads_postgres():
        if lead.phone_number in yielded:
            continue
        yield lead


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
