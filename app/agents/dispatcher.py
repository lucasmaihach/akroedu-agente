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

    # 5. Roteia para o agente especialista
    agent = AGENT_MAP.get(course)
    if agent is None:
        logger.error("Nenhum agente encontrado para o curso.", course=course)
        return

    # Verifica se o script ainda está ativo para passar o modo correto ao agente.
    # script_active=True significa que o AI deve ficar em modo silencioso (1-2 frases,
    # sem perguntas, sem revelar preço) porque o script de áudios ainda está conduzindo.
    # Isso deve ser True para TODOS os passos ANTES do passo de preço (passo 9),
    # independente de o trigger ser "auto" ou "response".
    from app.script.engine import SCRIPTS
    PRICE_REVEAL_STEP = 9  # índice do bloco 08 — Oferta de Preço + Urgência
    current_script = SCRIPTS.get(course)
    script_active = (
        current_script is not None
        and lead.script_step < len(current_script)
        and lead.script_step < PRICE_REVEAL_STEP
    )

    # Quando o próximo passo do script tem trigger="response", ele dispara imediatamente
    # após a mensagem do lead (via run_script_step no webhook). Esse passo já inclui
    # acolhimento (pre_text) + áudio + pergunta — a AI não precisa responder também.
    # Responder aqui geraria mensagem dupla: uma da AI e outra do script.
    if script_active and current_script is not None and lead.script_step < len(current_script):
        current_trigger = current_script[lead.script_step].get("trigger")
        if current_trigger == "response":
            logger.info(
                "Script response-trigger: AI silenciada para evitar mensagem dupla.",
                phone=lead.phone_number,
                step=lead.script_step,
            )
            return

    await agent.get_response(lead=lead, user_message=user_message, script_active=script_active)
