#!/usr/bin/env python3
"""
Script para testar os agentes localmente sem precisar de WhatsApp real.

Simula conversas com cada agente para validar respostas.

Uso:
    python scripts/test_agents.py
"""

import asyncio
from app.config import settings
from app.models.lead import Lead, CourseSlug, LeadStage
from app.memory.session import init_redis, get_or_create_lead, append_message, save_lead
from app.agents.courses.curso_1_agent import Curso1Agent
from app.agents.courses.curso_2_agent import Curso2Agent
from app.knowledge.base import load_knowledge


async def test_agent(agent, course_name: str):
    """Testa um agente com uma conversa simulada."""
    print(f"\n{'='*70}")
    print(f"🧪 Testando Agente: {course_name}")
    print(f"{'='*70}\n")

    # Cria um lead de teste
    phone = f"551100000000{hash(course_name) % 1000:03d}"
    lead = Lead(
        phone_number=phone,
        name="Cliente Teste",
        course_slug=agent.course_slug,
        stage=LeadStage.NURTURING,
    )

    # Simula uma conversa
    test_messages = [
        "Oi, tudo bem? Quanto custa o curso?",
        "Tem desconto se pagar à vista?",
        "Qual é a metodologia?",
        "Preciso de um tempo para pensar",
    ]

    for i, user_msg in enumerate(test_messages, 1):
        print(f"👤 Lead [{i}]: {user_msg}")

        # Append message
        await append_message(phone, role="user", content=user_msg)

        # Get response from agent
        knowledge = load_knowledge(agent.course_slug)
        response = await agent.respond(
            lead=lead,
            user_message=user_msg,
            knowledge=knowledge,
        )

        if response:
            print(f"🤖 Agente: {response}\n")
        else:
            print(f"🤖 Agente: [Escalado ou erro]\n")

        # Aguarda um pouco entre mensagens
        await asyncio.sleep(2)


async def main():
    print("🚀 Teste de Agentes")
    print(f"Model: {settings.anthropic_model}\n")

    # Inicializa Redis
    await init_redis()

    # Testa Curso 1
    agent1 = Curso1Agent()
    await test_agent(agent1, "Curso 1")

    # Testa Curso 2
    agent2 = Curso2Agent()
    await test_agent(agent2, "Curso 2")

    print(f"\n{'='*70}")
    print("✅ Testes concluídos!")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
