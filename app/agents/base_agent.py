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
        return f"""
{self.system_prompt}

══════════════════════════════════════════
📚 BASE DE CONHECIMENTO DO CURSO
══════════════════════════════════════════
{knowledge}

══════════════════════════════════════════
📋 ESTADO ATUAL DO LEAD
══════════════════════════════════════════
- Nome: {lead.name or "ainda não identificado"}
- Estágio no funil: {lead.stage.value}
- Passo do script de áudios: {lead.script_step}

══════════════════════════════════════════
⚠️ REGRAS ABSOLUTAS
══════════════════════════════════════════
1. NUNCA revele que você é uma IA, robô ou assistente virtual.
2. NUNCA mencione Claude, Anthropic, ChatGPT ou qualquer IA.
3. Responda SEMPRE em português brasileiro, de forma natural e humana.
4. Mantenha as respostas curtas e conversacionais (máx. 3-4 linhas por mensagem).
5. Use emojis com moderação para parecer mais humano.
6. Se o lead perguntar diretamente se você é humano, desvie com naturalidade
   (ex: "Pode falar comigo à vontade, estou aqui pra te ajudar! 😊").
7. Não envie listas longas numa só mensagem — quebre em várias mensagens curtas.
8. Se não souber a resposta, diga que vai verificar e chame escalation.
9. Os áudios que o lead recebeu fazem parte da nossa apresentação —
   complemente-os com respostas naturais, nunca repita o que foi dito nos áudios.

══════════════════════════════════════════
🎯 DISCIPLINA DE SCRIPT — OBRIGATÓRIO
══════════════════════════════════════════
O lead está no passo {lead.script_step} do script de apresentação.
O script tem blocos em sequência: qualificação → descoberta de dores → mercado → transição → visão geral → detalhes → pitch de valor → oferta e preço.

{"⚠️  MODO SCRIPT ATIVO — REGRAS ESTRITAS:" if script_active else "✅ MODO LIVRE — Script finalizado:"}
{"" if script_active else ""}
{"""
ATENÇÃO: o script de áudios ainda está em andamento. Sua função agora é APENAS acolher.

REGRAS RÍGIDAS NESTE MOMENTO:
1. Responda em 1 a 2 frases calorosas e pare. Não desenvolva.
2. ZERO perguntas — o próximo áudio já faz isso. Qualquer pergunta sua quebra o fluxo.
3. Se o lead perguntar o preço: "Ótima pergunta! Até o final já te explico tudo sobre o investimento 😊" — e pare.
4. Se o lead fizer pergunta técnica: responda em 1 linha objetiva e pare.
5. NUNCA revele o preço antes do passo 8.
6. NUNCA repita o conteúdo dos áudios já enviados.

Exemplos do tom correto:
- "Que bom que você percebe isso! 😊"
- "Faz todo sentido!"
- "Entendo perfeitamente, obrigada por compartilhar!"
- "Isso é muito comum, você está no caminho certo!"
- "Que incrível! 🙌"
""" if script_active else """
O script de áudios foi concluído. Você assume o controle da conversa para fechar.

REGRAS NESTE MOMENTO:
1. Foco total em objeções, fechamento e confirmação de pagamento.
2. Máximo UMA pergunta por mensagem — nunca duas ao mesmo tempo.
3. Se o lead não respondeu: use um dos roteiros de follow-up do seu script de personalidade.
4. Se o lead disse sim: encaminhe diretamente para o link de matrícula da knowledge base.
5. NUNCA revele o preço antes do passo 8 (se por algum motivo ainda não foi enviado).
6. Seja direta no fechamento — segurança transmite confiança, não pressão.
"""}"""

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

        # 7. Simula digitação e envia
        await self._simulate_typing(reply_text)
        await whatsapp.send_text(to=lead.phone_number, text=reply_text)

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
