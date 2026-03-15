# 📁 Estrutura Completa do Projeto

Visão geral de todos os arquivos e pastas do Sales Agent.

---

## 📦 Estrutura Raiz

```
sales-agent/
│
├── 📄 README.md                      # Documentação principal
├── 📄 QUICKSTART.md                  # Início rápido (10 min)
├── 📄 DEPLOYMENT.md                  # Guia de deploy em VPS
├── 📄 AGENT_TRAINING.md              # Como treinar os agentes
├── 📄 SETUP_AUDIOS.md                # Configurar áudios e upload
├── 📄 FAQ.md                         # Perguntas frequentes
├── 📄 PREPRODUCTION_CHECKLIST.md     # Checklist antes de ir ao vivo
├── 📄 STRUCTURE.md                   # Este arquivo
│
├── 📄 docker-compose.yml             # Orquestração de containers
├── 📄 Dockerfile                     # Imagem da aplicação
├── 📄 requirements.txt               # Dependências Python
├── 📄 env.example                    # Variáveis de ambiente (modelo)
├── 📄 .gitignore                     # O que NÃO commitar no Git
├── 📄 Makefile                       # Atalhos de comandos
├── 📄 alembic.ini                    # Configuração do Alembic (migrations)
│
├── 📄 test_webhook.sh                # Script para testar webhook
├── 📄 example.http                   # Exemplos de requisições HTTP
│
├── 📁 app/                           # Código principal da aplicação
│   ├── __init__.py
│   ├── main.py                       # FastAPI app entry point
│   ├── config.py                     # Pydantic Settings
│   │
│   ├── 📁 models/                    # Pydantic models (schemas)
│   │   ├── __init__.py
│   │   ├── message.py                # Meta webhook payloads
│   │   └── lead.py                   # Lead schema
│   │
│   ├── 📁 api/                       # FastAPI routers
│   │   ├── __init__.py
│   │   └── webhooks.py               # POST /webhook/whatsapp
│   │
│   ├── 📁 agents/                    # Agentes de IA
│   │   ├── __init__.py
│   │   ├── base_agent.py             # Classe base (BaseAgent)
│   │   ├── router_agent.py           # Identifica qual curso
│   │   ├── dispatcher.py             # Roteia para agente correto
│   │   │
│   │   └── 📁 courses/               # Agentes por curso
│   │       ├── __init__.py
│   │       ├── curso_1_agent.py      # Agente Curso 1
│   │       └── curso_2_agent.py      # Agente Curso 2
│   │
│   ├── 📁 knowledge/                 # Base de conhecimento dos cursos
│   │   ├── __init__.py
│   │   ├── base.py                   # Loader de .md files
│   │   │
│   │   └── 📁 courses/
│   │       ├── curso_1.md            # Info Curso 1 (EDITE AQUI!)
│   │       └── curso_2.md            # Info Curso 2 (EDITE AQUI!)
│   │
│   ├── 📁 memory/                    # Cache de sessão (Redis)
│   │   ├── __init__.py
│   │   └── session.py                # Lead cache + histórico
│   │
│   ├── 📁 script/                    # Motor de script de áudios
│   │   ├── __init__.py
│   │   ├── engine.py                 # Executa passos do script
│   │   │
│   │   └── 📁 schedules/             # Scripts por curso
│   │       ├── __init__.py
│   │       ├── curso_1_script.py     # Script Curso 1 (EDITE AQUI!)
│   │       └── curso_2_script.py     # Script Curso 2 (EDITE AQUI!)
│   │
│   ├── 📁 services/                  # Serviços externos
│   │   ├── __init__.py
│   │   ├── whatsapp.py               # Meta API (envio de msgs)
│   │   ├── crm.py                    # SprintHub API
│   │   └── escalation.py             # Lógica de escalação
│   │
│   └── 📁 db/                        # Banco de dados
│       ├── __init__.py
│       ├── database.py               # SQLAlchemy setup
│       └── orm_models.py             # Modelos ORM (Lead, Conversation, etc.)
│
├── 📁 scripts/                       # Scripts utilitários
│   ├── upload_audios.py              # Upload de áudios para Meta
│   ├── test_agents.py                # Testa agentes localmente
│   └── generate_report.py            # Gera relatórios de vendas
│
├── 📁 tests/                         # Testes unitários
│   ├── __init__.py
│   └── test_agents.py                # Testes dos agentes
│
├── 📁 audios/                        # Arquivos de áudio (NÃO commita!)
│   ├── curso_1/
│   │   ├── 01_boas_vindas.mp3
│   │   ├── 02_diferenciais.mp3
│   │   ├── 03_preco.mp3
│   │   ├── 04_depoimento.mp3
│   │   └── 05_cta_final.mp3
│   │
│   └── curso_2/
│       ├── 01_boas_vindas.mp3
│       ├── 02_mercado.mp3
│       ├── 03_grade.mp3
│       ├── 04_preco.mp3
│       └── 05_depoimento.mp3
│
└── 📁 backups/                       # Backups do banco (criado automaticamente)
    └── backup_20240101_120000.sql
```

---

## 📝 Arquivos Críticos para Editar

### 1️⃣ **Configuração (`.env`)**
Seu arquivo de credenciais e configuração (nunca commite!)

```env
META_VERIFY_TOKEN=...
META_ACCESS_TOKEN=...
ANTHROPIC_API_KEY=...
SPRINTHUB_API_KEY=...
DATABASE_URL=...
```

### 2️⃣ **Knowledge Base (Informações dos Cursos)**

**`app/knowledge/courses/curso_1.md`**
```markdown
# Curso 1 — [Nome]

## Investimento
## Diferenciais
## Grade Curricular
## Objeções Comuns
```

**`app/knowledge/courses/curso_2.md`**
```markdown
# Curso 2 — [Nome]
...
```

### 3️⃣ **Agentes (Personalidade dos Consultores)**

**`app/agents/courses/curso_1_agent.py`**
```python
class Curso1Agent(BaseAgent):
    system_prompt = """
    Você é [NOME], consultor de [CURSO]...
    """
```

**`app/agents/courses/curso_2_agent.py`**
```python
class Curso2Agent(BaseAgent):
    system_prompt = """
    Você é [NOME], consultor de [CURSO]...
    """
```

### 4️⃣ **Scripts de Áudios (Sequência de Envio)**

**`app/script/schedules/curso_1_script.py`**
```python
CURSO_1_SCRIPT = [
    {
        "delay_seconds": 2,
        "audio": "MEDIA_ID_AQUI",
        "trigger": "auto",
    },
    ...
]
```

**`app/script/schedules/curso_2_script.py`**
```python
CURSO_2_SCRIPT = [
    ...
]
```

---

## 🔑 Arquivos por Funcionalidade

### Webhook e Recebimento de Mensagens
```
app/api/webhooks.py                    # POST /webhook/whatsapp
app/models/message.py                  # Payload da Meta
```

### IA e Agentes
```
app/agents/base_agent.py               # Classe base
app/agents/router_agent.py             # Identifica curso
app/agents/dispatcher.py               # Roteia para agente
app/agents/courses/                    # Agentes específicos
```

### Áudios
```
app/script/engine.py                   # Executa passo do script
app/script/schedules/                  # Scripts por curso
scripts/upload_audios.py               # Upload para Meta
```

### Persistência (Redis + PostgreSQL)
```
app/memory/session.py                  # Cache Redis
app/db/database.py                     # PostgreSQL setup
app/db/orm_models.py                   # Modelos ORM
```

### Integrações Externas
```
app/services/whatsapp.py               # Meta API
app/services/crm.py                    # SprintHub API
app/services/escalation.py             # Escalação
```

---

## 📊 Fluxo de Dados

```
1. Lead envia mensagem via WhatsApp
   ↓
2. Meta API envia webhook → POST /webhook/whatsapp
   ↓
3. app/api/webhooks.py processa payload
   ↓
4. Cria/recupera lead no Redis (app/memory/session.py)
   ↓
5. Salva mensagem no histórico (Redis + PostgreSQL)
   ↓
6. app/agents/dispatcher.py roteia:
   - Novo lead? → router_agent identifica curso
   - Curso conhecido? → ativa agente especialista
   ↓
7. Agente (app/agents/courses/) chama Claude
   ↓
8. Claude retorna resposta
   ↓
9. app/services/whatsapp.py envia via Meta API
   ↓
10. app/services/crm.py sincroniza com SprintHub
    ↓
11. app/script/engine.py dispara próximo passo do script (áudio)
```

---

## 🗄️ Banco de Dados (PostgreSQL)

### Tabela: `leads`
```
id              | INTEGER (PK)
phone_number    | STRING (UNIQUE)
name            | STRING
course_slug     | STRING
stage           | STRING (new, nurturing, hot, converted, etc.)
sprinthub_id    | STRING
script_step     | INTEGER
is_escalated    | BOOLEAN
notes           | TEXT
created_at      | DATETIME
updated_at      | DATETIME
```

### Tabela: `conversations`
```
id              | INTEGER (PK)
phone_number    | STRING
role            | STRING (user / assistant)
content         | TEXT
created_at      | DATETIME
```

### Tabela: `audio_logs`
```
id              | INTEGER (PK)
phone_number    | STRING
course_slug     | STRING
script_step     | INTEGER
audio_filename  | STRING
sent_at         | DATETIME
```

---

## 🔄 Ciclo de Vida de um Lead

```
┌─────────────────────────────────────────┐
│ 1. NEW — Primeiro contato              │
│    (Agent: router — qual curso?)        │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 2. IDENTIFYING — Espera escolher curso │
│    (Agent: router asks)                 │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 3. NURTURING — Script de áudios começa │
│    (Agent: especialista + áudios)       │
└─────────────────────────────────────────┘
                  ↓
        ┌────────────────────┐
        │ Qual é o outcome?  │
        └────────────────────┘
       /                    \
      /                      \
  ┌──────────────┐       ┌─────────────┐
  │ OBJECTION    │       │ HOT         │
  │ ou           │       │ (interesse) │
  │ NEGOTIATING  │       └─────────────┘
  │ (preço)      │              ↓
  └──────────────┘       ┌─────────────────┐
        ↓                │ CONVERTED       │
        │                │ (fez matrícula) │
        │                └─────────────────┘
        │
  Lead quer humano?
        ↓
  ESCALATED (aguarda atendente)
```

---

## 🚀 Comandos Úteis

```bash
# Ver status
docker-compose ps

# Ver logs
docker-compose logs -f api

# Entrar no shell da API
docker-compose exec api /bin/bash

# Acessar banco de dados
docker-compose exec postgres psql -U sales_agent -d sales_agent_db

# Fazer backup
make backup-db

# Testar webhook
bash test_webhook.sh http://localhost:8000 5511999999999

# Upload de áudios
python scripts/upload_audios.py

# Gerar relatório
python scripts/generate_report.py --format html
```

---

## 📦 Dependências Principais

```
FastAPI              # Framework web
Anthropic Claude     # IA conversacional
Redis                # Cache de sessão
PostgreSQL           # Banco de dados persistente
SQLAlchemy           # ORM
httpx                # HTTP client (Meta API)
Pydantic             # Validação de dados
structlog            # Logging estruturado
```

Veja `requirements.txt` para lista completa.

---

## 🔒 Segurança

Arquivos que NÃO devem ser commitados:

```
.env                          # Credenciais
.env.local                    # Variáveis locais
*.sqlite                      # Banco SQLite local
__pycache__/                  # Cache Python
.vscode/                      # Configurações do IDE
audios/                       # Arquivos grandes
backups/                      # Backups do banco
.secrets/                     # Qualquer secrets
```

Veja `.gitignore`.

---

## 📚 Próximas Leituras

- **QUICKSTART.md** — Comece em 10 minutos
- **DEPLOYMENT.md** — Deploy em produção
- **AGENT_TRAINING.md** — Personalizar agentes
- **SETUP_AUDIOS.md** — Configurar áudios
- **FAQ.md** — Respostas a dúvidas comuns

---

**Pronto para explorar! 🚀**
