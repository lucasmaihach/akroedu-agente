import anthropic
import structlog
import asyncio
from typing import Optional

from app.config import settings
from app.models.lead import Lead, LeadStage
from app.memory.session import (
    get_history,
    update_lead_field,
)
from app.services import whatsapp, escalation
from app.services import crm
from app.services.error_alert import notify_conversation_error

logger = structlog.get_logger()

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

NON_SCRIPT_RESPONSE_DELAY_SECONDS = 2  # Espera principal é controlada no webhook (janela de 2 min)

# ── Classificador de intenção ────────────────────────────────────────────────
# Tool schema usado pelo classify_intent para forçar output estruturado via tool_use.
# tool_choice={"type":"tool","name":"classify"} garante que Claude SEMPRE preenche
# os campos — sem texto livre, sem JSON malformado.
_CLASSIFY_TOOL = {
    "name": "classify",
    "description": "Classifica a intenção da mensagem do lead e decide se o script deve avançar.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": [
                    "RESPOSTA_SCRIPT",    # lead respondeu o que foi perguntado
                    "MENSAGEM_GENERICA",  # qualquer outra coisa
                ],
                "description": "Classificação da intenção da mensagem.",
            },
            "advance_block": {
                "type": "boolean",
                "description": (
                    "true = lead respondeu de forma engajada (compartilhou algo, disse sim/ok/concordou). "
                    "false = lead foi evasivo, perguntou algo, respondeu com apenas 1-2 palavras vazias "
                    "ou a resposta não endereça o que foi perguntado no bloco atual."
                ),
            },
            "acolhimento_index": {
                "type": "integer",
                "minimum": 0,
                "maximum": 9,
                "description": (
                    "Índice (0-9) da variação de acolhimento pré-escrita que melhor combina "
                    "com o tom emocional da mensagem do lead. "
                    "0-2 = lead entusiasmado, animado ou muito positivo. "
                    "3-5 = lead neutro, objetivo ou direto. "
                    "6-7 = lead hesitante, com dúvida ou pouco engajado. "
                    "8-9 = lead reflexivo, analítico ou com objeção implícita."
                ),
            },
        },
        "required": ["intent", "advance_block", "acolhimento_index"],
    },
}

# ── Acolhimento ───────────────────────────────────────────────────────────────
# Propositalmente sem knowledge base — o LLM não deve ter acesso a nenhuma
# informação que possa "escapar" como preço ou detalhes do curso.
_ACOLHIMENTO_SYSTEM = (
    "Você é {agent_name}, consultora de matrículas.\n\n"
    "TAREFA ÚNICA: gere APENAS 1 frase curtíssima de acolhimento para a mensagem recebida.\n"
    "Contexto da intenção classificada: {intent}\n\n"
    "REGRAS ABSOLUTAS:\n"
    "- Máximo 1 frase, máximo 12 palavras\n"
    "- ZERO informações sobre o curso, preço, módulos ou qualquer conteúdo\n"
    "- ZERO perguntas\n"
    "- APENAS mostre que você leu e está presente\n"
    "- Linguagem calorosa e natural, português brasileiro\n"
    "- Não use travessão (—)\n\n"
    "EXEMPLOS CORRETOS:\n"
    "Faz todo sentido!\n"
    "Que bom que você trouxe isso 😊\n"
    "Entendo perfeitamente!\n"
    "Legal que você compartilhou isso!\n"
    "Isso é muito comum mesmo 😊\n\n"
    "EXEMPLOS ERRADOS (NUNCA FAÇA):\n"
    "❌ qualquer frase com preço, valor, R$, módulo, certificado\n"
    "❌ qualquer pergunta\n"
    "❌ mais de uma frase\n\n"
    "Responda APENAS com a frase de acolhimento, sem mais nada."
)


class BaseAgent:
    """
    Classe base para todos os agentes de venda.
    Cada agente de curso herda desta classe e sobrescreve:
      - course_slug: identificador do curso
      - system_prompt: personalidade + instruções específicas do curso
    """

    course_slug: str = "unknown"
    system_prompt: str = ""

    async def _simulate_typing(self, lead: Lead) -> None:
        """Mostra breve typing antes da resposta do agente."""
        if NON_SCRIPT_RESPONSE_DELAY_SECONDS > 0:
            await whatsapp.send_typing_and_wait(
                message_id=lead.last_received_msg_id or "",
                duration_seconds=NON_SCRIPT_RESPONSE_DELAY_SECONDS,
            )

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
                "5. NUNCA revele o preco — o script ainda nao chegou no bloco de oferta.\n"
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
                "5. Se o preco ainda nao foi revelado: nao revele — sinalize que vai verificar.\n"
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
            f"O lead está no passo {lead.script_step} do script de apresentação.\n\n"
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

    async def classify_intent(self, lead: Lead, user_message: str) -> dict:
        """
        Classifica a intenção da mensagem e decide se o bloco deve avançar.

        Usa tool_use com schema obrigatório — garante JSON válido sem retry.
        Modelo leve (Haiku) para custo e latência baixos.

        Retorna dict com:
          - intent: "RESPOSTA_SCRIPT" | "MENSAGEM_GENERICA"
          - advance_block: True se o lead respondeu suficientemente
        """
        system = (
            f"Você classifica mensagens de leads em um funil de vendas via WhatsApp.\n"
            f"Bloco atual do script: {lead.script_step}.\n\n"
            f"advance_block = true: lead respondeu de forma engajada "
            f"(compartilhou algo relevante, disse sim/ok, demonstrou interesse).\n"
            f"advance_block = false: lead foi evasivo, deu resposta de 1-2 palavras vazias, "
            f"mudou de assunto ou não endereçou o que foi perguntado."
        )
        try:
            history = await get_history(lead.phone_number, last_n=6)
            messages = history if history else [{"role": "user", "content": user_message}]
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                system=system,
                messages=messages,
                tools=[_CLASSIFY_TOOL],
                tool_choice={"type": "tool", "name": "classify"},
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "classify":
                    return block.input
        except Exception as e:
            logger.warning("Falha ao classificar intent — avançando por padrão.", error=str(e), phone=lead.phone_number)

        # Fallback seguro: assume que respondeu e avança
        return {"intent": "RESPOSTA_SCRIPT", "advance_block": True}

    async def generate_acolhimento(self, lead: Lead, user_message: str, intent: str = "RESPOSTA_SCRIPT") -> Optional[str]:
        """
        Gera 1 frase curta de acolhimento durante script ativo.

        max_tokens=80 é uma barreira física da API — impede geração longa
        independente do prompt ou de injeção adversarial.

        Retorna None em caso de erro (o script continua mesmo sem acolhimento).
        """
        agent_name = getattr(self, "agent_name", "Taynara")
        system = _ACOLHIMENTO_SYSTEM.format(agent_name=agent_name, intent=intent)
        try:
            history = await get_history(lead.phone_number, last_n=6)
            messages = history if history else [{"role": "user", "content": user_message}]
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=80,
                system=system,
                messages=messages,
            )
            if not response.content or not hasattr(response.content[0], "text"):
                return None
            return response.content[0].text.strip()
        except Exception as e:
            logger.warning("Falha ao gerar acolhimento — script continua.", error=str(e), phone=lead.phone_number)
            return None

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

        # 3. Monta o histórico para enviar ao Claude
        history = await get_history(lead.phone_number, last_n=20)

        # 4. Chama o Claude
        system = self._build_system_prompt(lead, knowledge, script_active=script_active)
        try:
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=512,
                system=system,
                messages=history,
            )
            if not response.content or not hasattr(response.content[0], 'text'):
                raise ValueError("Claude retornou formato inesperado")
            reply_text = response.content[0].text.strip()
        except Exception as e:
            logger.error("❌ Erro ao chamar Claude.", error=str(e))
            await notify_conversation_error(
                source="anthropic.reply",
                error=e,
                phone=lead.phone_number,
                lead_name=lead.name,
                stage=lead.stage.value,
                user_message=user_message,
                extra={"course": self.course_slug},
            )
            reply_text = (
                "Oi! Tive um probleminha aqui, mas já estou resolvendo. "
                "Pode me mandar sua dúvida de novo? 😊"
            )

        # 5. Simula digitação e envia — divide em bolhas separadas por linha
        try:
            await self._simulate_typing(lead)
            bubbles = [line for line in reply_text.split("\n") if line.strip()]
            for i, bubble in enumerate(bubbles):
                await whatsapp.send_text(to=lead.phone_number, text=bubble)
                if i < len(bubbles) - 1:
                    await asyncio.sleep(1.2)
        except Exception as e:
            logger.error("❌ Erro ao enviar resposta para o lead.", error=str(e), phone=lead.phone_number)
            await notify_conversation_error(
                source="whatsapp.send_text.agent_reply",
                error=e,
                phone=lead.phone_number,
                lead_name=lead.name,
                stage=lead.stage.value,
                user_message=user_message,
                extra={"reply_preview": reply_text[:120]},
            )
            return None

        # 6. Sincroniza com CRM
        await crm.sync_lead(lead)

        logger.info(
            "🤖 Agente respondeu.",
            phone=lead.phone_number,
            course=self.course_slug,
            stage=lead.stage.value,
            preview=reply_text[:60],
        )

        return reply_text
