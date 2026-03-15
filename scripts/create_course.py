#!/usr/bin/env python3
"""
Gerador de novo curso para o Sales Agent.

Cria automaticamente todos os arquivos necessários para um novo curso
e mostra as linhas que precisam ser adicionadas manualmente.

Uso:
    python scripts/create_course.py --slug curso_3 --name "MBA em Gestão" --consultant "Julia"
    python scripts/create_course.py --slug mba_direito --name "Pós em Direito Empresarial" --consultant "Roberto"
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def create_knowledge(slug: str, name: str):
    path = ROOT / "app" / "knowledge" / "courses" / f"{slug}.md"
    if path.exists():
        print(f"  ⚠️  Já existe: {path.relative_to(ROOT)}")
        return

    content = f"""# {name}

> ⚠️ Preencha com as informações reais do curso.

## Informações Gerais
- **Nome completo:** {name}
- **Modalidade:** EAD / Presencial / Híbrido
- **Duração:** [Ex: 12 meses]
- **Carga horária:** [Ex: 360h]
- **Início das aulas:** [Ex: Todo mês / Data específica]
- **Certificado:** Reconhecido pelo MEC

## Investimento
- **Valor total:** R$ [valor]
- **Parcelamento:** Em até [X]x de R$ [valor da parcela]
- **Desconto à vista:** [X]%
- **Condições especiais:** [Ex: Desconto para quem fechar até sexta-feira]

## Diferenciais do Curso
- [Diferencial 1]
- [Diferencial 2]
- [Diferencial 3]
- [Diferencial 4]

## Grade Curricular (principais disciplinas)
1. [Disciplina 1]
2. [Disciplina 2]
3. [Disciplina 3]
4. [Disciplina 4]
5. [Disciplina 5]

## Público-alvo
- [Perfil 1 — ex: Profissionais de gestão que querem se especializar]
- [Perfil 2]
- [Perfil 3]

## Corpo Docente
- Professores com experiência de mercado
- [Destaque de algum professor famoso ou referência, se houver]

## Depoimentos de Alunos
> "[Depoimento 1]" — Nome, Cargo

> "[Depoimento 2]" — Nome, Cargo

## Objeções Comuns e Como Responder

### "Está caro"
Entendo que o investimento precisa fazer sentido! Mas pensa comigo: essa pós-graduação
vai abrir portas que podem transformar sua carreira. Temos condições facilitadas em até [X]x.

### "Não tenho tempo"
Nossa metodologia foi pensada para quem tem agenda cheia.
As aulas são [ao vivo/gravadas] e você assiste no seu ritmo, de qualquer lugar.

### "Vou pensar"
Claro, faz sentido pensar! Só que as vagas são limitadas e as condições que te apresentei
são especiais para essa semana. Posso te ajudar com mais alguma informação?

### "Já tenho graduação, preciso de pós?"
A pós-graduação hoje não é mais diferencial, é requisito mínimo no mercado competitivo.
Empresas top pagam em média [X]% a mais para profissionais pós-graduados.

## Link de Matrícula
[URL do link de matrícula ou pagamento]

## Contato para Dúvidas Específicas
[Telefone ou e-mail do setor de matrículas]
"""
    path.write_text(content, encoding="utf-8")
    print(f"  ✅ Criado: {path.relative_to(ROOT)}")


def create_agent(slug: str, name: str, consultant: str):
    class_name = "".join(word.capitalize() for word in slug.split("_")) + "Agent"
    path = ROOT / "app" / "agents" / "courses" / f"{slug}_agent.py"
    if path.exists():
        print(f"  ⚠️  Já existe: {path.relative_to(ROOT)}")
        return

    content = f'''from app.agents.base_agent import BaseAgent
from app.knowledge.base import load_knowledge
from app.models.lead import Lead


class {class_name}(BaseAgent):
    """
    Agente especialista em {name}.
    Personalize o system_prompt com a personalidade real do consultor.
    """

    course_slug = "{slug}"

    system_prompt = """
Você é {consultant}, consultor(a) de matrículas especialista no curso {name}.

Sua personalidade:
- [Descreva a personalidade aqui — ex: calorosa, empática, entusiasmada]
- [Tom de voz — ex: simples, próxima, sem jargões]
- [Abordagem — ex: escuta ativamente e conecta benefícios às dores do lead]
- [Postura diante de objeções — ex: não pressiona, cria urgência com naturalidade]

Seu objetivo principal:
Conduzir o lead até a matrícula de forma consultiva, entendendo o momento de vida dele
e mostrando como esse curso vai transformar a carreira/vida dele.

Fluxo ideal da conversa:
1. Boas-vindas calorosas e identificar o nome do lead
2. Entender o momento de vida / objetivo profissional do lead
3. Apresentar o curso conectando aos objetivos do lead
4. Quebrar objeções com empatia
5. Apresentar condições de pagamento e criar urgência
6. Direcionar para o link de matrícula

Lembre-se: você já enviou áudios de apresentação para esse lead.
Não repita o que foi dito nos áudios — complemente com informações personalizadas.
"""

    async def get_response(self, lead: Lead, user_message: str) -> str | None:
        knowledge = load_knowledge(self.course_slug)
        return await self.respond(
            lead=lead,
            user_message=user_message,
            knowledge=knowledge,
        )
'''
    path.write_text(content, encoding="utf-8")
    print(f"  ✅ Criado: {path.relative_to(ROOT)}")
    return class_name


def create_script(slug: str, name: str):
    var_name = slug.upper() + "_SCRIPT"
    path = ROOT / "app" / "script" / "schedules" / f"{slug}_script.py"
    if path.exists():
        print(f"  ⚠️  Já existe: {path.relative_to(ROOT)}")
        return

    content = f'''"""
Script de áudios de {name}.

Cada passo do script é um dicionário com:
  - delay_seconds (int)  : tempo de espera ANTES de enviar este passo
  - pre_text (str|None)  : texto enviado ANTES do áudio (opcional)
  - audio (str|None)     : URL pública ou media_id do áudio na Meta (opcional)
  - post_text (str|None) : texto enviado APÓS o áudio (opcional)
  - trigger (str)        : "auto"     → dispara automaticamente após o delay
                           "response" → só dispara quando o lead responder algo

Como usar:
  1. Grave os áudios e coloque em audios/{slug}/
  2. Faça upload: python scripts/upload_audios.py
  3. Copie os media_ids gerados e substitua os valores abaixo.
"""

{var_name}: list[dict] = [
    # ── Passo 0 — Boas-vindas imediatas ──────────────────────────────────────
    {{
        "delay_seconds": 2,
        "pre_text": "Oi! Que ótimo ter você aqui 🎉 Deixa eu te contar tudo sobre o nosso curso!",
        "audio": "MEDIA_ID_AUDIO_BOAS_VINDAS_{slug.upper()}",   # substitua pelo media_id real
        "post_text": "Ouviu? O que achou? 😊 Pode me fazer qualquer pergunta!",
        "trigger": "auto",
    }},

    # ── Passo 1 — Diferenciais (após resposta do lead) ────────────────────────
    {{
        "delay_seconds": 0,
        "pre_text": None,
        "audio": "MEDIA_ID_AUDIO_DIFERENCIAIS_{slug.upper()}",  # substitua pelo media_id real
        "post_text": (
            "Esses são os nossos principais diferenciais! 🚀\\n"
            "Tem alguma dúvida sobre a grade ou metodologia?"
        ),
        "trigger": "response",
    }},

    # ── Passo 2 — Investimento (2 min após o passo anterior) ─────────────────
    {{
        "delay_seconds": 120,
        "pre_text": "Agora vou te falar sobre o investimento e nossas condições especiais 💰",
        "audio": "MEDIA_ID_AUDIO_PRECO_{slug.upper()}",         # substitua pelo media_id real
        "post_text": (
            "Condições bem acessíveis né? 😊\\n"
            "Quer que eu te envie o link de matrícula?"
        ),
        "trigger": "auto",
    }},

    # ── Passo 3 — Depoimento (após resposta do lead) ──────────────────────────
    {{
        "delay_seconds": 0,
        "pre_text": "Olha o que um dos nossos alunos tem a dizer 👇",
        "audio": "MEDIA_ID_AUDIO_DEPOIMENTO_{slug.upper()}",    # substitua pelo media_id real
        "post_text": None,
        "trigger": "response",
    }},

    # ── Passo 4 — CTA final (5 min após o passo anterior) ────────────────────
    {{
        "delay_seconds": 300,
        "pre_text": None,
        "audio": None,
        "post_text": (
            "Oi! Passando pra te lembrar que as vagas com desconto são limitadas 🔥\\n"
            "Já pensou na sua decisão? Posso te ajudar com mais alguma coisa?"
        ),
        "trigger": "auto",
    }},
]
'''
    path.write_text(content, encoding="utf-8")
    print(f"  ✅ Criado: {path.relative_to(ROOT)}")


def create_audio_dir(slug: str):
    audio_dir = ROOT / "audios" / slug
    audio_dir.mkdir(parents=True, exist_ok=True)
    gitkeep = audio_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()
    print(f"  ✅ Criado: audios/{slug}/")


def print_manual_steps(slug: str, name: str, class_name: str):
    enum_value = slug.upper()

    print(f"""
{'='*65}
📋 PASSOS MANUAIS — adicione as linhas abaixo em cada arquivo:
{'='*65}

1️⃣  app/models/lead.py  →  dentro do CourseSlug(str, Enum):
    {enum_value} = "{slug}"

2️⃣  app/agents/dispatcher.py  →  no topo (imports):
    from app.agents.courses.{slug}_agent import {class_name}

    →  dentro do AGENT_MAP:
    CourseSlug.{enum_value}: {class_name}(),

3️⃣  app/agents/router_agent.py  →  dentro de COURSES_DESCRIPTION:
    - {slug}: {name} — [descreva em uma frase]

4️⃣  app/config.py  →  adicione ao .env (e ao env.example):
    SPRINTHUB_PIPELINE_{enum_value}=id-do-pipeline-aqui

5️⃣  app/services/crm.py  →  dentro de PIPELINE_BY_COURSE:
    "{slug}": settings.sprinthub_pipeline_{slug},

{'='*65}
""")


def main():
    parser = argparse.ArgumentParser(
        description="Cria os arquivos de um novo curso para o Sales Agent."
    )
    parser.add_argument("--slug", required=True, help="Identificador único do curso (ex: mba_gestao)")
    parser.add_argument("--name", required=True, help="Nome completo do curso (ex: 'MBA em Gestão')")
    parser.add_argument("--consultant", default="[Nome do Consultor]", help="Nome do consultor virtual")
    args = parser.parse_args()

    slug = args.slug.lower().replace("-", "_").replace(" ", "_")
    name = args.name
    consultant = args.consultant

    # Valida slug
    if not slug.replace("_", "").isalnum():
        print(f"❌ Slug inválido: '{slug}'. Use apenas letras, números e underscore.")
        sys.exit(1)

    print(f"\n🚀 Criando arquivos para: {name} (slug: {slug})\n")

    create_knowledge(slug, name)
    class_name = create_agent(slug, name, consultant)
    create_script(slug, name)
    create_audio_dir(slug)

    print_manual_steps(slug, name, class_name)
    print("✅ Pronto! Siga os passos manuais acima para finalizar o cadastro do curso.\n")


if __name__ == "__main__":
    main()
