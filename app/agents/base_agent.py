import anthropic
import structlog
import asyncio
from typing import Optional

from app.config import settings
from app.models.lead import Lead, LeadStage
from app.memory.session import (
    get_history,
    append_message,
    update_lead_field,
    save_lead,
)
from app.services import whatsapp, escalation
from app.services import crm

logger = structlog.get_logger()

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# Delay simulado de digitação (ms por caractere, com limites)
TYPING_DELAY_PER_CHAR = 0.03  # 30ms por caractere
TYPING_MIN_DELAY = 1.0         # mínimo 1 segundo
TYPING_MAX_DELAY = 4.0         # máximo 4 segundos


class BaseAgent:
    """
    Classe base para todos os agentes de venda.
    Cada agente de curso herda desta classe e sobrescreve:
      - course_slug: identificador do curso
      - system_prompt: personalidade + instruções específicas do curso
    """

    course_slug: str = "unknown"
    system_prompt: str = ""

    async def _simulate_typing(self, text: str) -> None:
        """Aguarda um tempo proporcional ao tamanho da resposta antes de enviar."""
        delay = len(text) * TYPING_DELAY_PER_CHAR
        delay = max(TYPING_MIN_DELAY, min(delay, TYPING_MAX_DELAY))
        await asyncio.sleep(delay)

    def _build_system_prompt(self, lead: Lead, knowledge: str, script_active: bool = False) -> str:
        """
        Monta o system prompt final combinando:
        - Personalidade do agente (definida na subclasse)
        - Knowledge base do curso
        - Estado atual do lead (nome, estágio, script_step)
        """
        if script_active:
            script_mode_header = "MODO SCRIPT ATIVO — REGRAS ESTRITAS:"
            script_mode_body = (
                "ATENCAO: o script de audios ainda esta em andamento. Sua funcao agora e APENAS acolher.\n\n"
                "REGRAS RIGIDAS NESTE MOMENTO:\n"
                "1. Responda em 1 a 2 frases calorosas e pare. Nao desenvolva.\n"
                "2. ZERO perguntas — o proximo audio ja faz isso. Qualquer pergunta sua quebra o fluxo.\n"
                "3. Se o lead perguntar o preco: \"Otima pergunta! Ate o final ja te explico tudo sobre o investimento\" — e pare.\n"
                "4. Se o lead fizer pergunta tecnica: responda em 1 linha objetiva e pare.\n"
                "5. NUNCA revele o preco antes do passo 8.\n"
                "6. NUNCA repita o conteudo dos audios ja enviados.\n\n"
                "Exemplos do tom correto:\n"
                "- \"Que bom que voce percebe isso! 😊\"\n"
                "- \"Faz todo sentido!\"\n"
                "- \"Entendo perfeitamente, obrigada por compartilhar!\"\n"
                "- \"Isso e muito comum, voce esta no caminho certo!\"\n"
                "- \"Que incrivel! 🙌\""
            )
        else:
            script_mode_header = "MODO LIVRE — Script finalizado:"
            script_mode_body = (
                "O script de audios foi concluido. Voce assume o controle da conversa para fechar.\n\n"
                "REGRAS NESTE MOMENTO:\n"
                "1. Foco total em objecoes, fechamento e confirmacao de pagamento.\n"
                "2. Maximo UMA pergunta por mensagem — nunca duas ao mesmo tempo.\n"
                "3. Se o lead nao respondeu: use um dos roteiros de follow-up do seu script de personalidade.\n"
                "4. Se o lead disse sim: encaminhe diretamente para o link de matricula da knowledge base.\n"
                "5. NUNCA revele o preco antes do passo 8 (se por algum motivo ainda nao foi enviado).\n"
                "6. Seja direta no fechamento — seguranca transmite confianca, nao pressao."
            )

        return (
            f"{self.system_prompt}\n\n"
            f"══════════════════════════════════════════\n"
            f"📚 BASE DE CONHECIMENTO DO CURSO\n"
            f"══════════════════════════════════════════\n"
            f"{knowledge}\n\n"
            f"══════════════════════════════════════════\n"
            f"📋 ESTADO ATUAL DO LEAD\n"
            f"══════════════════════════════════════════\n"
            f"- Nome: {lead.name or 'ainda não identificado'}\n"
            f"- Estágio no funil: {lead.stage.value}\n"
            f"- Passo do script de áudios: {lead.script_step}\n\n"
            f"══════════════════════════════════════════\n"
            f"⚠️ REGRAS ABSOLUTAS\n"
            f"══════════════════════════════════════════\n"
            f"1. NUNCA revele que você é uma IA, robô ou assistente virtual.\n"
            f"2. NUNCA mencione Claude, Anthropic, ChatGPT ou qualquer IA.\n"
            f"3. Responda SEMPRE em português brasileiro, de forma natural e humana.\n"
            f"4. Mantenha as respostas curtas e conversacionais (máx. 3-4 linhas por mensagem).\n"
            f"5. Use emojis com moderação para parecer mais humano.\n"
            f"6. Se o lead perguntar diretamente se você é humano, desvie com naturalidade\n"
            f"   (ex: \"Pode falar comigo à vontade, estou aqui pra te ajudar! 😊\").\n"
            f"7. Não envie listas longas numa só mensagem — quebre em várias mensagens curtas.\n"
            f"8. Se não souber a resposta, diga que vai verificar e chame escalation.\n"
            f"9. Os áudios que o lead recebeu fazem parte da nossa apresentação —\n"
            f"   complemente-os com respostas naturais, nunca repita o que foi dito nos áudios.\n"
            f"10. NUNCA use travessão (—) em nenhuma mensagem. Use vírgula, ponto final ou\n"
            f"    quebra de linha no lugar. Pessoas não usam travessão em conversas de WhatsApp.\n"
            f"11. NUNCA invente ou assuma informações que não estão explicitamente na base de\n"
            f"    conhecimento acima. Se o lead perguntar algo que não está lá, diga que vai\n"
            f"    verificar e acione escalação para não prometer algo errado.\n\n"
            f"══════════════════════════════════════════\n"
            f"🎯 DISCIPLINA DE SCRIPT — OBRIGATÓRIO\n"
            f"══════════════════════════════════════════\n"
            f"O lead está no passo {lead.script_step} do script de apresentação.\n"
            f"O script tem blocos em sequência: qualificação → descoberta de dores → mercado "
            f"→ transição → visão geral → detalhes → pitch de valor → oferta e preço.\n\n"
            f"{script_mode_header}\n"
            f"{script_mode_body}"
        )

    async def _detect_and_update_stage(self, lead: Lead, text: str) -> Lead:
        """
        Analisa a mensagem e atualiza o estágio do lead se necessário.
        """
        lower = text.lower()

        # Objeção de preço
        if any(w in lower for w in ["caro", "preço", "valor", "quanto", "desconto", "parcel"]):
            if lead.stage not in (LeadStage.NEGOTIATING, LeadStage.CONVERTED):
                lead = await update_lead_field(lead.phone_number, stage=LeadStage.OBJECTION)

        # Lead quente
        elif any(w in lower for w in ["quero", "tenho interesse", "me inscrever", "matricular", "como faço"]):
            lead = await update_lead_field(lead.phone_number, stage=LeadStage.HOT)

        # Em negociação
        elif any(w in lower for w in ["parcela", "boleto", "pix", "cartão", "forma de pagamento"]):
            lead = await update_lead_field(lead.phone_number, stage=LeadStage.NEGOTIATING)

        # Convertido
        elif any(w in lower for w in ["paguei", "efetuei", "realizei o pagamento", "fiz a matrícula"]):
            lead = await update_lead_field(lead.phone_number, stage=LeadStage.CONVERTED)

        return lead

    async def respond(
        self,
        lead: Lead,
        user_message: str,
        knowledge: str,
        script_active: bool = False,
    ) -> Optional[str]:
        """
        Processa a mensagem do lead e retorna a resposta do agente.
        Também gerencia:
          - Histórico de conversa
          - Atualização de estágio
          - Escalação para humano
          - Envio da resposta via WhatsApp
        """
        # 1. Verifica se deve escalar para humano
        if escalation.should_escalate_by_message(user_message):
            updated_lead = await escalation.escalate(lead, reason="Lead pediu atendimento humano")
            await crm.sync_lead(updated_lead)
            return None  # escalation já enviou mensagem

        # 2. Atualiza o estágio do lead com base na mensagem
        lead = await self._detect_and_update_stage(lead, user_message)

        # 3. Salva a mensagem do usuário no histórico
        await append_message(lead.phone_number, role="user", content=user_message)

        # 4. Monta o histórico para enviar ao Claude
        history = await get_history(lead.phone_number, last_n=20)

        # 5. Chama o Claude
        system = self._build_system_prompt(lead, knowledge, script_active=script_active)
        try:
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=512,
                system=system,
                messages=history,
            )
            reply_text = response.content[0].text.strip()
        except Exception as e:
            logger.error("❌ Erro ao chamar Claude.", error=str(e))
            reply_text = (
                "Oi! Tive um probleminha aqui, mas já estou resolvendo. "
                "Pode me mandar sua dúvida de novo? 😊"
            )

        # 6. Salva a resposta no histórico
        await append_message(lead.phone_number, role="assistant", content=reply_text)

        # 7. Simula digitação e envia — divide em bolhas separadas por linha
        await self._simulate_typing(reply_text)
        bubbles = [line for line in reply_text.split("\n") if line.strip()]
        for i, bubble in enumerate(bubbles):
            await whatsapp.send_text(to=lead.phone_number, text=bubble)
            if i < len(bubbles) - 1:
                await asyncio.sleep(1.2)

        # 8. Sincroniza com CRM
        await crm.sync_lead(lead)

        logger.info(
            "🤖 Agente respondeu.",
            phone=lead.phone_number,
            course=self.course_slug,
            stage=lead.stage.value,
            preview=reply_text[:60],
        )

        return reply_text
