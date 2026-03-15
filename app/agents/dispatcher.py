import structlog

from app.models.lead import Lead, CourseSlug, LeadStage
from app.agents.router_agent import identify_course
from app.agents.courses.curso_1_agent import Curso1Agent
from app.agents.courses.curso_2_agent import Curso2Agent
from app.agents.courses.pos_fisio_neuro_agent import PosFisioNeuroAgent
from app.memory.session import update_lead_field, save_lead
from app.services import whatsapp

logger = structlog.get_logger()

# Palavras que indicam que o lead está perguntando sobre preço
_PRICE_KEYWORDS = [
    "preço", "preco", "valor", "quanto", "custa", "custo",
    "investimento", "parcela", "mensalidade", "boleto", "pix",
]


def _is_asking_price(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in _PRICE_KEYWORDS)

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


async def dispatch(lead: Lead, user_message: str) -> bool:
    """
    Ponto central de despacho de mensagens.
    1. Identifica o curso de interesse via router
    2. Roteia para o agente especialista correto
    3. Se não identificar, faz pergunta de qualificação

    Retorna True se o script deve avançar normalmente,
    False se o dispatch já tratou a mensagem e o script NÃO deve avançar.
    """

    # 1. Se lead foi escalado, ignora mensagens (humano está cuidando)
    if lead.is_escalated:
        logger.info("Lead escalado, mensagem ignorada.", phone=lead.phone_number)
        return False

    # 2. Identifica o curso de interesse
    course = await identify_course(lead, user_message)

    # 3. Se não identificou ainda, pede para o lead escolher
    if course == CourseSlug.UNKNOWN:
        if lead.stage == LeadStage.NEW:
            # Primeiro contato — envia boas-vindas
            lead = await update_lead_field(
                lead.phone_number,
                stage=LeadStage.IDENTIFYING,
            )
            await whatsapp.send_text(to=lead.phone_number, text=_build_welcome_message())
        else:
            # Lead já está em conversa mas não identificou o curso
            await whatsapp.send_text(
                to=lead.phone_number,
                text=(
                    "Pode me contar um pouquinho mais sobre o que você está buscando? "
                    "Assim consigo te ajudar melhor! 😊"
                ),
            )
        return False

    # 4. Atualiza o estágio para NURTURING se ainda estava em IDENTIFYING/NEW
    is_first_contact = lead.stage in (LeadStage.NEW, LeadStage.IDENTIFYING)
    if is_first_contact:
        lead = await update_lead_field(
            lead.phone_number,
            stage=LeadStage.NURTURING,
            course_slug=course,
        )
        # Primeiro contato: o script engine (step 0) envia o BLOCO 1 de boas-vindas.
        # Não chamamos o agente aqui para evitar mensagem dupla.
        logger.info("Primeiro contato — aguardando script engine enviar BLOCO 1.", phone=lead.phone_number)
        return True  # avança o script normalmente (vai rodar BLOCO 1)

    # 5. Roteia para o agente especialista
    agent = AGENT_MAP.get(course)
    if agent is None:
        logger.error("Nenhum agente encontrado para o curso.", course=course)
        return False

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
    # completamente silenciada — EXCETO quando o lead pergunta sobre preço.
    if script_active:
        if _is_asking_price(user_message):
            # Lead perguntou o preço durante o script
            price_ask_count = lead.price_ask_count + 1
            lead = await update_lead_field(lead.phone_number, price_ask_count=price_ask_count)

            if price_ask_count == 1:
                # Primeira vez: redireciona com leveza, aguarda resposta
                # NÃO avança o script — aguarda a próxima resposta do lead
                await whatsapp.send_text(
                    to=lead.phone_number,
                    text=(
                        "Claro, saber o preço é super importante! 😊\n"
                        "Posso te contar como funciona antes? "
                        "Assim você consegue avaliar muito melhor se o investimento faz sentido pra você."
                    ),
                )
                logger.info(
                    "💰 Lead perguntou preço (1ª vez) — redirecionado, script pausado.",
                    phone=lead.phone_number,
                    step=lead.script_step,
                )
                return False  # não avança o script

            else:
                # Segunda vez ou mais: cede e pula para o bloco de detalhes do curso
                await whatsapp.send_text(
                    to=lead.phone_number,
                    text="Claro, vou te explicar! 😊",
                )
                await update_lead_field(lead.phone_number, script_step=price_skip_to_step)
                logger.info(
                    "💰 Lead insistiu no preço (2ª vez) — pulando para bloco de preço.",
                    phone=lead.phone_number,
                    new_step=price_skip_to_step,
                )
                return True  # avança (agora está no bloco configurado)

        logger.info(
            "Script ativo: AI silenciada, avançando script.",
            phone=lead.phone_number,
            step=lead.script_step,
        )
        return True  # mensagem normal durante script — avança normalmente

    await agent.get_response(lead=lead, user_message=user_message, script_active=script_active)
    return True
