import re
import random

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
from app.utils.gender_detection import adapt_gender_text, detect_gender_from_name
from app.knowledge.base import load_knowledge

logger = structlog.get_logger()

FAQ_RESPONSE_DELAY_SECONDS = 60

# ── Variações para perguntas fora do FAQ ──────────────────────────────────────
# Cada vez que o lead faz uma pergunta fora do FAQ, uma variação diferente é enviada
# para não parecer automatizado quando a situação se repete na mesma conversa.
# Padrões para detectar quando o lead informa ou corrige o próprio nome no chat.
_NAME_CORRECTION_PATTERNS = [
    re.compile(r'\bmeu nome [eé] ([A-ZÀ-Úa-zà-ú][A-ZÀ-Úa-zà-ú\s]{1,29})', re.IGNORECASE),
    re.compile(r'\bme chamo ([A-ZÀ-Úa-zà-ú][A-ZÀ-Úa-zà-ú\s]{1,29})', re.IGNORECASE),
    re.compile(r'\bpode me chamar de ([A-ZÀ-Úa-zà-ú][A-ZÀ-Úa-zà-ú\s]{1,29})', re.IGNORECASE),
    re.compile(r'\bpode chamar de ([A-ZÀ-Úa-zà-ú][A-ZÀ-Úa-zà-ú\s]{1,29})', re.IGNORECASE),
]

_OUT_OF_FAQ_RESPONSES = [
    "Entendi sua dúvida! Vou anotar aqui e te respondo direitinho. Enquanto isso, vou te mandar os próximos detalhes 😊",
    "Boa pergunta! Já já eu te respondo certinho. Enquanto isso, vou seguir te mandando mais informações 😊",
    "Perfeito, anotei sua pergunta aqui. Vou te responder com precisão já já — e vou seguir com os próximos pontos 😊",
    "Entendi! Pra não te passar nada errado, vou te responder direitinho já já. Enquanto isso, sigo com mais detalhes 😊",
]

# Rastreia o índice da última variação enviada por lead (evita repetição consecutiva).
# Vive só em memória — reinicia com o container, o que é aceitável.
_last_out_of_faq_index: dict[str, int] = {}


def _pick_out_of_faq_response(phone: str, gender: str = "male") -> str:
    """
    Seleciona uma variação diferente da última enviada para este lead,
    garantindo que a mesma frase nunca se repita em sequência.
    Adapta o gênero conforme necessário.
    """
    last = _last_out_of_faq_index.get(phone, -1)
    available = [i for i in range(len(_OUT_OF_FAQ_RESPONSES)) if i != last]
    chosen = random.choice(available)
    _last_out_of_faq_index[phone] = chosen
    response = _OUT_OF_FAQ_RESPONSES[chosen]
    return adapt_gender_text(response, gender)


# ── Detecção de respostas simples afirmativas ─────────────────────────────────
# Leads que respondem "sim", "ok", "pode" etc. não precisam de análise LLM.
# O engine usa seleção por hash das variações pré-definidas no script.
_PUNCTUATION_RE = re.compile(r"[^\w\s]")

_SIMPLE_AFFIRMATIVE_WORDS = {
    "sim", "ok", "okay", "pode", "claro", "certo", "entendi",
    "entendo", "beleza", "boa", "otimo", "ótimo", "perfeito",
    "vai", "vamos", "quero", "show", "top", "legal",
    "ta", "tá", "faz", "conta", "fala", "adorei", "gostei",
    "com certeza", "pode ser", "pode falar", "pode continuar",
    "me conta", "me fala", "faz sentido", "quero sim",
    "continua", "me mostra", "me fale", "boa escolha",
}

_SIMPLE_AFFIRMATIVE_STARTERS = {
    "sim", "ok", "pode", "claro", "certo", "vai", "quero",
    "show", "top", "boa", "otimo", "ótimo",
}

_QUESTION_STEM_HINTS = {
    "quanto",
    "qual",
    "quais",
    "como",
    "quando",
    "onde",
    "porque",
    "por que",
    "valor",
    "preco",
    "preço",
    "instagram",
    "modulo",
    "módulo",
}

_CONTINUE_HINTS = {
    "continua",
    "continuar",
    "seguir",
    "segue",
    "prosseguir",
    "avancar",
    "avançar",
    "manda",
    "enviar",
}


def _is_simple_affirmative(text: str) -> bool:
    """
    Detecta respostas curtas e afirmativas que não precisam de análise LLM.
    Frases com mais de 5 palavras sempre passam pelo classify_intent.
    """
    cleaned = _PUNCTUATION_RE.sub("", text.lower().strip())
    words = cleaned.split()
    if not words or len(words) > 5:
        return False
    if cleaned in _SIMPLE_AFFIRMATIVE_WORDS:
        return True
    # Frase curta (≤3 palavras) iniciada por palavra claramente afirmativa
    return len(words) <= 3 and words[0] in _SIMPLE_AFFIRMATIVE_STARTERS


def _normalize_micro(text: str) -> str:
    cleaned = _PUNCTUATION_RE.sub(" ", (text or "").lower().strip())
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_continue_signal(text: str) -> bool:
    """
    Sinais de continuidade ("pode continuar", "segue", "manda", "pode seguir").
    Isso não é pergunta técnica — é permissão para avançar no trilho.
    """
    t = _normalize_micro(text)
    if not t:
        return False
    signals = {
        "pode continuar",
        "pode seguir",
        "segue",
        "continua",
        "pode ir",
        "vai",
        "vamos",
        "manda",
        "pode mandar",
        "pode enviar",
        "pode sim",
        "sim pode",
        "sim",
        "ok",
        "certo",
        "beleza",
    }
    if t in signals:
        return True

    # Cobertura para confirmações curtas com pequenas variações:
    # "sim pode continuar", "pode seguir então", "ok, manda".
    words = t.split()
    if not words:
        return False

    if "?" in (text or ""):
        return False

    has_continue_hint = any(w in _CONTINUE_HINTS for w in words)
    has_affirmative_start = words[0] in _SIMPLE_AFFIRMATIVE_STARTERS
    has_question_hint = any(h in t for h in _QUESTION_STEM_HINTS)

    return (has_continue_hint and has_affirmative_start and not has_question_hint) or (
        len(words) <= 4 and has_continue_hint and not has_question_hint
    )


def _pick_variation(
    script: list[dict],
    step: int,
    index: int | None,
    lead_name: str | None = None,
) -> str | None:
    """
    Seleciona a variação de acolhimento pré-escrita para o step atual.

    - Usa o índice retornado pelo classify_intent quando válido.
    - Fallback para seleção por hash do step quando índice é None ou inválido.
    - Substitui [nome] pelo primeiro nome do lead.
    - Converte list[str] em string única (as variações podem ser listas de bolhas).
    """
    if not script or step >= len(script):
        return None

    variations = script[step].get("acolhimento_variations")
    if not variations:
        return None

    if index is not None and 0 <= index < len(variations):
        selected = variations[index]
    else:
        selected = variations[step % len(variations)]

    # Variação pode ser str ou list[str] — junta em string única
    text = " ".join(selected) if isinstance(selected, list) else selected

    # Substitui placeholder de nome
    if lead_name:
        nome = lead_name.strip().split()[0]
        text = text.replace("[nome]", nome)
    else:
        text = text.replace(", [nome]", "").replace("[nome]", "").strip()

    return text


# Palavras/frases que indicam que a pessoa é um aluno atual buscando suporte pós-venda.
_STUDENT_SUPPORT_KEYWORDS = [
    "acesso a plataforma", "acesso à plataforma", "login da plataforma", "login e senha",
    "não consigo acessar", "nao consigo acessar",
    "meu acesso", "minha senha", "esqueci a senha",
    "link de acesso", "dados de acesso",
    "já sou aluno", "ja sou aluno", "já estou matriculado", "ja estou matriculado",
    "já paguei", "ja paguei", "já me matriculei", "ja me matriculei",
    "prova do módulo", "prova do modulo", "fazer a prova", "nota da prova",
    "fui reprovado", "fui reprovada", "reprovado", "reprovada",
    "pdr", "pedido de reconsideração",
    "atividade de extensão", "atividade de extensao",
    "boleto do curso", "boleto da mensalidade", "segunda via do boleto",
    "cnpj da faculdade", "cnpj da instituição", "cnpj para imposto",
    "imposto de renda", "declaração do imposto", "informe de rendimentos",
    "comprovante de pagamento", "recibo do pagamento",
    "certificado", "quando sai o certificado", "diploma",
    "plataforma do curso", "plataforma de ensino",
]


def _is_student_support(text: str) -> bool:
    """Detecta mensagens de alunos atuais buscando suporte pós-venda."""
    lower = text.lower()
    return any(kw in lower for kw in _STUDENT_SUPPORT_KEYWORDS)


# Palavras/frases que indicam que o lead está perguntando sobre o preço do curso.
# "valor" e "quanto" sozinhos são genéricos demais (ex: "meu valor por hora", "quanto tempo").
# Usamos frases mais específicas para evitar falsos positivos.
_PRICE_KEYWORDS = [
    "preço", "preco",
    "quanto custa", "quanto é", "quanto fica", "quanto tá", "quanto ta",
    "custa", "custo",
    "investimento",
    "parcela", "mensalidade",
    "boleto", "pix",
    "qual o valor", "qual valor", "me fala o valor", "me fala o preço",
    "quanto seria", "quanto custaria",
]


def _is_asking_price(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _PRICE_KEYWORDS)


# Saudações sociais com "?" que não são perguntas técnicas.
# Ex: "tudo bem e você?", "como você está?", "oi, tudo bem?"
_SOCIAL_GREETING_PATTERNS = [
    "tudo bem", "tudo bom", "como vai", "como voce", "como você",
    "oi tudo", "olá tudo", "ola tudo", "bom dia", "boa tarde", "boa noite",
    "tá bem", "ta bem", "está bem",
]


def _is_social_greeting(text: str) -> bool:
    """Detecta saudações sociais que contêm '?' mas não são perguntas técnicas."""
    cleaned = _PUNCTUATION_RE.sub(" ", text.lower().strip())
    return any(pat in cleaned for pat in _SOCIAL_GREETING_PATTERNS)


def _looks_like_question(text: str) -> bool:
    lower = text.lower().strip()

    # Respostas curtas afirmativas ("pode continuar", "ok", "sim") não são perguntas.
    if _is_simple_affirmative(lower):
        return False

    # Saudações sociais com "?" não devem ser tratadas como perguntas técnicas.
    if "?" in lower and _is_social_greeting(lower):
        return False

    if "?" in lower:
        return True

    tokens = [t for t in lower.replace("?", " ").split() if t]
    if not tokens:
        return False

    # "pode me X" frequentemente é pedido/pergunta mesmo sem "?":
    # ex.: "pode me mandar a grade", "pode me explicar", "pode me dizer".
    if tokens[0] == "pode" and len(tokens) >= 3 and tokens[1] in {"me", "nos"}:
        action_terms = {
            "mandar",
            "enviar",
            "passar",
            "explicar",
            "dizer",
            "falar",
            "mostrar",
            "informar",
        }
        if any(t in action_terms for t in tokens[2:]):
            return True

    # Começos de pergunta mais confiáveis (evita falso positivo em frases afirmativas).
    question_starters = {"como", "quando", "quanto", "qual", "quais", "onde", "porque", "funciona", "posso", "precisa"}
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

    # 1a. Detecta correção de nome ("meu nome é X", "me chamo X", "pode me chamar de X")
    for _pattern in _NAME_CORRECTION_PATTERNS:
        _m = _pattern.search(user_message)
        if _m:
            new_name = _m.group(1).strip().rstrip(".!?,;")
            if new_name and new_name.lower() != (lead.name or "").lower():
                new_gender = detect_gender_from_name(new_name)
                lead = await update_lead_field(lead.phone_number, name=new_name, gender=new_gender)
                logger.info("Nome do lead atualizado.", phone=lead.phone_number, new_name=new_name, gender=new_gender)
            break

    # 1b. Detecta alunos atuais buscando suporte pós-venda
    if _is_student_support(user_message):
        await whatsapp.send_text(
            to=lead.phone_number,
            text="Olá! Vou verificar isso pra você e já te respondo. 😊",
        )
        await escalation.notify_human_only(
            lead=lead,
            reason="Aluno atual buscando suporte pós-venda",
            user_message=user_message,
        )
        logger.info("🎓 Suporte de aluno detectado — humano notificado.", phone=lead.phone_number)
        return False, None

    # 2. Identifica o curso de interesse
    course = await identify_course(lead, user_message)

    # 3. Se não identificou o produto, ignora silenciosamente — sem enviar nenhuma mensagem.
    if course == CourseSlug.UNKNOWN:
        logger.info(
            "Lead sem produto mapeado — mensagem ignorada silenciosamente.",
            phone=lead.phone_number,
        )
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
                    # Adapta gênero
                    faq_acolhimento = adapt_gender_text(faq_acolhimento, lead.gender)
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
        # Avisa o lead, notifica humano e continua o script normalmente.
        # O script não para — muitos leads fazem uma pergunta e somem se não receberem
        # mais conteúdo. O humano responde a dúvida em paralelo.
        # ── RESPOSTA SIMPLES (camada 4a) ─────────────────────────────────────────
        # "sim", "ok", "pode", "entendi", "faz sentido" etc.
        # Não precisa de LLM — engine seleciona variação por hash.
        if _is_simple_affirmative(user_message):
            logger.info(
                "✅ Resposta simples afirmativa — LLM ignorado, avançando script.",
                phone=lead.phone_number,
                step=lead.script_step,
                message=user_message[:30],
            )
            return True, None

        # Sinal claro de continuidade: força avanço sem cair em "pergunta fora do FAQ".
        if _is_continue_signal(user_message):
            logger.info(
                "➡️ Sinal de continuidade — avançando script.",
                phone=lead.phone_number,
                step=lead.script_step,
                message=user_message[:40],
            )
            return True, None

        if _looks_like_question(user_message):
            # Tenta responder com segurança usando histórico + knowledge base.
            knowledge = load_knowledge(getattr(agent, "course_slug", course.value))
            current_question = _get_current_closing_question(lead, current_script) or _get_pending_engagement_question(lead, current_script)
            decision = await agent.script_context_decision(
                lead=lead,
                user_message=user_message,
                knowledge=knowledge,
                current_question=current_question,
            )

            reply = (decision.get("reply") or "").strip()
            can_answer = bool(decision.get("can_answer"))
            should_advance = bool(decision.get("should_advance", True))
            notify_human = bool(decision.get("notify_human", False))

            # Barreira física contra vazamento de preço.
            reply = output_guard.sanitize(reply) or ""
            if can_answer and reply:
                reply = adapt_gender_text(reply, lead.gender)
                delay = whatsapp.estimate_typing_delay(reply)
                await whatsapp.send_typing_and_wait(lead.last_received_msg_id or "", delay)
                await whatsapp.send_text(to=lead.phone_number, text=reply)
                logger.info(
                    "Resposta contextual enviada durante script ativo.",
                    phone=lead.phone_number,
                    step=lead.script_step,
                    notify_human=notify_human,
                    should_advance=should_advance,
                    decision_reason=decision.get("reason", ""),
                )
            else:
                # Sem base segura: fallback + notifica humano.
                fallback = _pick_out_of_faq_response(lead.phone_number, lead.gender)
                await whatsapp.send_text(to=lead.phone_number, text=fallback)
                notify_human = True
                logger.info(
                    "Pergunta fora do FAQ sem base segura — fallback enviado.",
                    phone=lead.phone_number,
                    step=lead.script_step,
                    decision_reason=decision.get("reason", ""),
                )

            if notify_human:
                await escalation.notify_human_only(
                    lead=lead,
                    reason="Pergunta fora do FAQ durante script ativo (decisão contextual)",
                    user_message=user_message,
                )

            return should_advance, None

        # ── CLASSIFICAÇÃO (camada 4b) ────────────────────────────────────────────
        # Haiku classifica a intenção via tool_use (JSON garantido) e escolhe o
        # índice da variação de acolhimento pré-escrita que melhor combina com
        # o tom da mensagem — zero geração livre, zero risco de vazar preço.
        current_question = _get_current_closing_question(lead, current_script) or _get_pending_engagement_question(lead, current_script)
        classification = await agent.classify_intent(lead=lead, user_message=user_message, current_question=current_question)
        intent = classification.get("intent", "RESPOSTA_SCRIPT")
        advance_block = classification.get("advance_block", True)
        acolhimento_index = classification.get("acolhimento_index", None)

        # Resolve o índice em texto usando a lista pré-escrita do step atual
        acolhimento = _pick_variation(current_script, lead.script_step, acolhimento_index, lead.name)

        # ── advance_block=False: lead foi evasivo ────────────────────────────
        # Envia o acolhimento e re-pergunta o fechamento do bloco atual.
        # O engine não é chamado — o script não avança.
        if not advance_block:
            if acolhimento:
                # Adapta gênero
                acolhimento = adapt_gender_text(acolhimento, lead.gender)
                delay = whatsapp.estimate_typing_delay(acolhimento)
                await whatsapp.send_typing_and_wait(lead.last_received_msg_id or "", delay)
                await whatsapp.send_text(to=lead.phone_number, text=acolhimento)

            closing = _get_current_closing_question(lead, current_script)
            if closing:
                # Adapta gênero
                closing = adapt_gender_text(closing, lead.gender)
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
            "Script ativo — variação selecionada, bloco avança.",
            phone=lead.phone_number,
            step=lead.script_step,
            intent=intent,
            acolhimento_index=acolhimento_index,
            acolhimento_preview=(acolhimento or "")[:60],
        )
        return True, acolhimento

    await agent.get_response(lead=lead, user_message=user_message, script_active=script_active)
    return True, None
