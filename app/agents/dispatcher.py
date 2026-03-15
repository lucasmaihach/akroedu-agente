import structlog

from app.models.lead import Lead, CourseSlug, LeadStage
from app.agents.router_agent import identify_course
from app.agents.courses.curso_1_agent import Curso1Agent
from app.agents.courses.curso_2_agent import Curso2Agent
from app.agents.courses.pos_fisio_neuro_agent import PosFisioNeuroAgent
from app.memory.session import update_lead_field, save_lead
from app.services import whatsapp

logger = structlog.get_logger()

# Mapa de curso → agente instanciado
AGENT_MAP = {
    CourseSlug.CURSO_1: Curso1Agent(),
    CourseSlug.CURSO_2: Curso2Agent(),
    CourseSlug.POS_FISIO_NEURO: PosFisioNeuroAgent(),
}

# Mensagem de boas-vindas quando o curso ainda não foi identificado
WELCOME_MESSAGE = (
    "Oi! Tudo bem? 😊 Que bom que você entrou em contato!\n\n"
    "Me conta, qual dos nossos cursos de pós-graduação você quer saber mais?\n"
    "Temos a *Pós-Graduação em Fisioterapia Neurofuncional*. "
    "Qual deles chamou mais atenção pra você?"
)


async def dispatch(lead: Lead, user_message: str) -> None:
    """
    Ponto central de despacho de mensagens.
    1. Identifica o curso de interesse via router
    2. Roteia para o agente especialista correto
    3. Se não identificar, faz pergunta de qualificação
    """

    # 1. Se lead foi escalado, ignora mensagens (humano está cuidando)
    if lead.is_escalated:
        logger.info("Lead escalado, mensagem ignorada.", phone=lead.phone_number)
        return

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
            await whatsapp.send_text(to=lead.phone_number, text=WELCOME_MESSAGE)
        else:
            # Lead já está em conversa mas não identificou o curso
            await whatsapp.send_text(
                to=lead.phone_number,
                text=(
                    "Pode me contar um pouquinho mais sobre o que você está buscando? "
                    "Assim consigo te ajudar melhor! 😊"
                ),
            )
        return

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
        return

    # 5. Verifica se o script irá tratar esta mensagem
    # Exceção: objeções, perguntas de preço ou pedido de humano sempre ativam a IA
    OVERRIDE_KEYWORDS = [
        "caro", "preço", "valor", "quanto custa", "quanto é", "investimento",
        "desconto", "parcel", "pagar", "não tenho", "nao tenho",
        "não posso", "nao posso", "preciso pensar", "vou pensar",
        "humano", "atendente", "pessoa real", "falar com alguém",
    ]
    message_lower = user_message.lower()
    has_override = any(kw in message_lower for kw in OVERRIDE_KEYWORDS)

    from app.script.engine import SCRIPTS
    current_script = SCRIPTS.get(course)
    if current_script and lead.script_step < len(current_script) and not has_override:
        current_step = current_script[lead.script_step]
        if current_step.get("trigger") == "response":
            logger.info(
                "Script irá tratar esta mensagem — agente silenciado.",
                phone=lead.phone_number,
                step=lead.script_step,
            )
            return

    if has_override:
        logger.info(
            "Palavra-chave de objeção detectada — IA assume mesmo durante script.",
            phone=lead.phone_number,
            step=lead.script_step,
        )

    # 6. Script finalizado ou passo sem trigger "response" — agente assume
    agent = AGENT_MAP.get(course)
    if agent is None:
        logger.error("Nenhum agente encontrado para o curso.", course=course)
        return

    await agent.get_response(lead=lead, user_message=user_message)
