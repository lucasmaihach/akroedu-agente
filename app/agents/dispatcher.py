from datetime import timedelta

import structlog

from app.models.lead import Lead, CourseSlug, LeadStage
from app.agents.router_agent import identify_course
from app.agents.courses.curso_1_agent import Curso1Agent
from app.agents.courses.curso_2_agent import Curso2Agent
from app.agents.courses.pos_fisio_neuro_agent import PosFisioNeuroAgent
from app.memory.session import update_lead_field
from app.services import whatsapp
from app.services import escalation
from app.services import output_guard
from app.agents.courses.pos_fisio_neuro_faq import match_faq_response
from app.utils.business_hours import is_within_business_hours, now_utc
from app.jobs.store import schedule_faq_reply_resume

logger = structlog.get_logger()

FAQ_RESPONSE_DELAY_SECONDS = 60

# Palavras que indicam que o lead está perguntando sobre preço
_PRICE_KEYWORDS = [
    "preço", "preco", "valor", "quanto", "custa", "custo",
    "investimento", "parcela", "mensalidade", "boleto", "pix",
]


def _is_asking_price(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in _PRICE_KEYWORDS)


def _looks_like_question(text: str) -> bool:
    lower = text.lower().strip()
    if "?" in lower:
        return True

    tokens = [t for t in lower.replace("?", " ").split() if t]
    if not tokens:
        return False

    # Começos de pergunta mais confiáveis (evita falso positivo em frases afirmativas).
    question_starters = {"como", "quando", "quanto", "qual", "quais", "onde", "porque", "funciona", "posso", "pode", "precisa"}
    if tokens[0] in question_starters:
        return True

    # "por" sozinho gera muito falso-positivo (ex: "por isso estou interessada").
    if lower.startswith("por que") or lower.startswith("por quê"):
        return True

    # Apenas termos que indicam dúvida real sobre políticas.
    # Preço/mensalidade/valor são tratados pela camada de proteção de preço antes de chegar aqui.
    strong_terms = {"cancelamento", "cancelar", "reembolso", "multa"}
    return any(t in strong_terms for t in tokens)


def _extract_last_question(text_or_list) -> str | None:
    """Retorna a última bolha que contém interrogação, se existir."""
    if not text_or_list:
        return None

    items = text_or_list if isinstance(text_or_list, list) else [text_or_list]
    for item in reversed(items):
        if isinstance(item, str) and "?" in item:
            return item.strip()
    return None


def _get_pending_engagement_question(lead: Lead, script: list[dict]) -> str | None:
    """
    Tenta recuperar a última pergunta de engajamento do bloco anterior.
    Usado quando o lead interrompe com FAQ para respondermos a dúvida
    e depois puxarmos de volta para o roteiro sem avançar etapa.
    """
    if lead.script_step <= 0 or lead.script_step > len(script):
        return None

    previous_step = script[lead.script_step - 1]
    for field in ("post_text", "mid_text", "pre_text"):
        question = _extract_last_question(previous_step.get(field))
        if question:
            return question

    return None


def _get_current_closing_question(lead: Lead, script: list[dict]) -> str | None:
    """
    Retorna a pergunta de fechamento do bloco atual para reenviar quando
    o lead responde de forma evasiva (advance_block=False).

    Prioriza post_text (última coisa enviada no bloco), depois mid_text.
    Se for lista, retorna o último item.
    """
    if script is None or lead.script_step >= len(script):
        return None

    current_step = script[lead.script_step]
    for field in ("post_text", "mid_text"):
        value = current_step.get(field)
        if not value:
            continue
        if isinstance(value, list):
            return value[-1] if value else None
        return value

    return None



# Mapa de curso → agente instanciado
AGENT_MAP = {
    CourseSlug.CURSO_1: Curso1Agent(),
    CourseSlug.CURSO_2: Curso2Agent(),
    CourseSlug.POS_FISIO_NEURO: PosFisioNeuroAgent(),
}

def _build_welcome_message() -> str:
    """
    Monta a mensagem de boas-vindas listando os cursos disponíveis dinamicamente.
    Para adicionar um novo curso, basta registrá-lo em engine.SCRIPT_CONFIGS
    com o campo 'name' — a mensagem passa a incluí-lo automaticamente.
    """
    from app.script.engine import SCRIPT_CONFIGS
    course_names = [
        f"• *{cfg['name']}*"
        for cfg in SCRIPT_CONFIGS.values()
        if cfg.get("name") and not cfg["name"].startswith("[")
    ]
    courses_block = "\n".join(course_names) if course_names else "• Nossos cursos de pós-graduação"
    return (
        "Oi! Tudo bem? 😊 Que bom que você entrou em contato!\n\n"
        "Me conta, qual dos nossos cursos você quer saber mais?\n\n"
        f"{courses_block}\n\n"
        "Qual deles chamou mais atenção pra você?"
    )


async def dispatch(lead: Lead, user_message: str) -> tuple[bool, str | None]:
    """
    Ponto central de despacho de mensagens.
    1. Identifica o curso de interesse via router
    2. Roteia para o agente especialista correto
    3. Se não identificar, faz pergunta de qualificação

    Retorna (should_advance_script, acolhimento_text):
    - should_advance_script: True se o engine deve rodar o próximo passo do script
    - acolhimento_text: frase curta gerada pelo LLM para substituir as acolhimento_variations
      do script (None quando não se aplica — o engine usa as variações pré-definidas)
    """

    # 1. Se lead foi escalado, ignora mensagens (humano está cuidando)
    if lead.is_escalated:
        logger.info("Lead escalado, mensagem ignorada.", phone=lead.phone_number)
        return False, None

    # 2. Identifica o curso de interesse
    course = await identify_course(lead, user_message)

    # 3. Se não identificou ainda, pede para o lead escolher
    if course == CourseSlug.UNKNOWN:
        if lead.stage == LeadStage.NEW:
            # Primeiro contato — envia boas-vindas apenas no horário comercial
            if not is_within_business_hours(now_utc()):
                logger.info(
                    "Lead novo fora do horário comercial — boas-vindas não enviada.",
                    phone=lead.phone_number,
                )
                return False, None

            lead = await update_lead_field(
                lead.phone_number,
                stage=LeadStage.IDENTIFYING,
            )
            await whatsapp.send_text(to=lead.phone_number, text=_build_welcome_message())
        else:
            # Lead já está em conversa mas não identificou o curso.
            # Evita repetir a mesma pergunta em curto intervalo por reentregas/eventos duplicados.
            now = now_utc()
            if lead.last_unknown_prompt_at and (now - lead.last_unknown_prompt_at) < timedelta(hours=2):
                logger.info(
                    "Prompt de identificação suprimido para evitar repetição.",
                    phone=lead.phone_number,
                    last_unknown_prompt_at=str(lead.last_unknown_prompt_at),
                )
                return False, None

            await whatsapp.send_text(
                to=lead.phone_number,
                text=(
                    "Pode me contar um pouquinho mais sobre o que você está buscando? "
                    "Assim consigo te ajudar melhor! 😊"
                ),
            )
            await update_lead_field(lead.phone_number, last_unknown_prompt_at=now)
        return False, None

    # 4. Atualiza o estágio para NURTURING se ainda estava em IDENTIFYING/NEW
    is_first_contact = lead.stage in (LeadStage.NEW, LeadStage.IDENTIFYING)
    if is_first_contact:
        lead = await update_lead_field(
            lead.phone_number,
            stage=LeadStage.NURTURING,
            course_slug=course,
            last_unknown_prompt_at=None,
        )
        # Primeiro contato: o script engine (step 0) envia o BLOCO 1 de boas-vindas.
        # Não chamamos o agente aqui para evitar mensagem dupla.
        logger.info("Primeiro contato — aguardando script engine enviar BLOCO 1.", phone=lead.phone_number)
        return True, None  # avança o script normalmente (vai rodar BLOCO 1)

    # 5. Roteia para o agente especialista
    agent = AGENT_MAP.get(course)
    if agent is None:
        logger.error("Nenhum agente encontrado para o curso.", course=course)
        return False, None

    # Verifica se o script ainda está ativo para passar o modo correto ao agente.
    # script_active=True significa que o AI deve ficar em modo silencioso (1-2 frases,
    # sem perguntas, sem revelar preço) porque o script de áudios ainda está conduzindo.
    # Os limiares de passo são definidos por curso no próprio arquivo do script.
    from app.script.engine import SCRIPTS, SCRIPT_CONFIGS
    course_config = SCRIPT_CONFIGS.get(course, {})
    price_reveal_step = course_config.get("price_reveal_step", 999)
    price_skip_to_step = course_config.get("price_skip_to_step", 0)

    current_script = SCRIPTS.get(course)
    script_active = (
        current_script is not None
        and lead.script_step < len(current_script)
        and lead.script_step < price_reveal_step
    )

    # Enquanto o script estiver ativo (qualquer step antes do preço), a AI fica
    # silenciada. O único papel do LLM é gerar 1 frase de acolhimento.
    if script_active:
        # ── ESCALAÇÃO (prioridade máxima — lead pediu atendimento humano explicitamente) ──
        if escalation.should_escalate_by_message(user_message):
            updated_lead = await escalation.escalate(lead, reason="Lead pediu atendimento humano durante script")
            from app.services import crm
            await crm.sync_lead(updated_lead)
            logger.info("🚨 Lead escalado durante script ativo.", phone=lead.phone_number)
            return False, None

        # ── PROTEÇÃO DE PREÇO (camada 1 — hardcoded, imune a qualquer LLM/FAQ) ──
        if _is_asking_price(user_message):
            new_count = lead.price_ask_count + 1
            lead = await update_lead_field(lead.phone_number, price_ask_count=new_count)

            if new_count < 2:
                # Primeira pergunta de preço: reconhece e segue o script na ordem normal.
                await whatsapp.send_text(
                    to=lead.phone_number,
                    text="Já vou chegar nos valores, prometo! 😊 Me deixa te mostrar mais um pouquinho antes.",
                )
                logger.info(
                    "💰 Preço perguntado pela 1ª vez — acknowledged, script segue na ordem.",
                    phone=lead.phone_number,
                    price_ask_count=new_count,
                )
            else:
                # Segunda pergunta de preço: pula para o bloco de preço.
                await whatsapp.send_text(
                    to=lead.phone_number,
                    text="Tá bom! Já te falo sobre o investimento 😊",
                )
                await update_lead_field(lead.phone_number, script_step=price_skip_to_step)
                logger.info(
                    "💰 Preço perguntado pela 2ª vez — pulando para step de preço.",
                    phone=lead.phone_number,
                    new_step=price_skip_to_step,
                    price_ask_count=new_count,
                )
            return True, None

        # ── FAQ (camada 2 — intents de preço excluídos durante script ativo) ──
        if course == CourseSlug.POS_FISIO_NEURO:
            faq_response, notify_human = match_faq_response(user_message, exclude_price=True)
            if faq_response:
                # Gera acolhimento antes da resposta para não parecer mensagem seca/robótica.
                faq_acolhimento = await agent.generate_acolhimento(
                    lead=lead,
                    user_message=user_message,
                    intent="MENSAGEM_GENERICA",
                )
                faq_acolhimento = output_guard.sanitize(faq_acolhimento)
                if faq_acolhimento:
                    delay = whatsapp.estimate_typing_delay(faq_acolhimento)
                    await whatsapp.send_typing_and_wait(lead.last_received_msg_id or "", delay)
                    await whatsapp.send_text(to=lead.phone_number, text=faq_acolhimento)

                await schedule_faq_reply_resume(
                    phone=lead.phone_number,
                    faq_response=faq_response,
                    user_message=user_message,
                    notify_human=notify_human,
                    expected_script_step=lead.script_step,
                    delay_seconds=FAQ_RESPONSE_DELAY_SECONDS,
                )
                logger.info(
                    "FAQ detectado durante script ativo; acolhimento enviado, resposta agendada.",
                    phone=lead.phone_number,
                    step=lead.script_step,
                    notify_human=notify_human,
                )
                return False, None

        # ── PERGUNTA FORA DO FAQ (camada 3) ──────────────────────────────────
        # Verificado ANTES do classify+acolhimento para evitar chamadas LLM desnecessárias
        # e garantir que o script NÃO avança — o lead precisa de resposta humana primeiro.
        if _looks_like_question(user_message):
            await whatsapp.send_text(
                to=lead.phone_number,
                text="Vou verificar isso pra você e já te respondo! 😊",
            )
            await escalation.notify_human_only(
                lead=lead,
                reason="Pergunta fora do FAQ durante script ativo",
                user_message=user_message,
            )
            logger.info(
                "Pergunta fora do FAQ — lead avisado + humano notificado, script pausado.",
                phone=lead.phone_number,
                step=lead.script_step,
            )
            return False, None

        # ── CLASSIFICAÇÃO + ACOLHIMENTO (camada 4) ──────────────────────────────
        # Duas chamadas LLM separadas com papéis distintos:
        #   A) Haiku classifica a intenção e decide se o bloco avança (JSON via tool_use)
        #   B) Haiku gera 1 frase de acolhimento contextual (max_tokens=80, barreira física)
        # Ambas recebem histórico recente para ter contexto do que foi perguntado antes.

        classification = await agent.classify_intent(lead=lead, user_message=user_message)
        intent = classification.get("intent", "RESPOSTA_SCRIPT")
        advance_block = classification.get("advance_block", True)

        acolhimento = await agent.generate_acolhimento(
            lead=lead,
            user_message=user_message,
            intent=intent,
        )
        # Validação de segurança: descarta silenciosamente se o LLM vazar preço
        acolhimento = output_guard.sanitize(acolhimento)

        # ── advance_block=False: lead foi evasivo ────────────────────────────
        # Envia o acolhimento e re-pergunta o fechamento do bloco atual.
        # O engine não é chamado — o script não avança.
        if not advance_block:
            if acolhimento:
                delay = whatsapp.estimate_typing_delay(acolhimento)
                await whatsapp.send_typing_and_wait(lead.last_received_msg_id or "", delay)
                await whatsapp.send_text(to=lead.phone_number, text=acolhimento)

            closing = _get_current_closing_question(lead, current_script)
            if closing:
                await whatsapp.send_typing_and_wait(lead.last_received_msg_id or "", 1.5)
                await whatsapp.send_text(to=lead.phone_number, text=closing)

            logger.info(
                "Lead evasivo — bloco não avança, closing question reenviada.",
                phone=lead.phone_number,
                step=lead.script_step,
                intent=intent,
            )
            return False, None

        logger.info(
            "Script ativo — acolhimento gerado, bloco avança.",
            phone=lead.phone_number,
            step=lead.script_step,
            intent=intent,
            advance_block=advance_block,
            acolhimento_preview=(acolhimento or "")[:60],
        )
        return True, acolhimento

    await agent.get_response(lead=lead, user_message=user_message, script_active=script_active)
    return True, None
