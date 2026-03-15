# 🤖 Sales Agent — Pós-Graduação via WhatsApp

Agente de vendas inteligente para cursos de pós-graduação via WhatsApp, usando Claude IA, Meta API oficial e gerenciamento de leads em SprintHub.

## 🎯 Características

✅ **IA Conversacional com Claude Sonnet** — Respostas naturais, parecem de um vendedor humano
✅ **Múltiplos Agentes Especializados** — Cada curso com seu próprio agente com personalidade
✅ **Script de Áudios Automático** — Áudios pré-gravados disparados em sequência temporal ou por gatilhos
✅ **Roteador Inteligente** — Identifica automaticamente qual curso o lead está interessado
✅ **Escalação para Humano** — Se o lead pedir, transfere para um atendente real
✅ **Integração SprintHub** — Leads sincronizados automaticamente no seu CRM
✅ **Memória de Conversa** — Redis cacheando histórico para respostas personalizadas
✅ **Meta API Oficial** — Sem dependências de APIs de terceiros, direto com WhatsApp

---

## 🏗️ Arquitetura

```
WhatsApp (Lead)
    ↓
[Meta API Webhook] → FastAPI
    ↓
[Session Manager - Redis] ← histórico
    ↓
[Router Agent] ← identifica curso
    ↓
[Agente Especialista] ← Claude IA + Knowledge Base
    ├→ [Script Engine] ← dispara áudios
    ├→ [CRM Sync] ← SprintHub
    └→ [Escalation] ← transfere para humano
```

---

## 📋 Pré-requisitos

- **Python 3.11+**
- **Docker & Docker Compose** (para dev local)
- **Conta Meta/WhatsApp Business** com API oficial configurada
- **API Key da Anthropic (Claude)**
- **API Key do SprintHub**
- **VPS (Hostinger)** para produção

---

## 🚀 Quick Start (Local com Docker)

### 1️⃣ Clone e configure

```bash
git clone <seu-repo>
cd sales-agent
cp env.example .env
```

### 2️⃣ Preencha o `.env`

```bash
# WhatsApp Meta API
META_VERIFY_TOKEN=seu-token
META_ACCESS_TOKEN=seu-token-permanente
META_PHONE_NUMBER_ID=seu-id
META_API_VERSION=v20.0

# Claude
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5

# Banco de dados
DATABASE_URL=postgresql+asyncpg://sales_agent:senha@postgres:5432/sales_agent_db
POSTGRES_USER=sales_agent
POSTGRES_PASSWORD=senha-forte

# Redis
REDIS_URL=redis://redis:6379/0

# SprintHub
SPRINTHUB_API_KEY=sua-chave
SPRINTHUB_PIPELINE_CURSO_1=pipeline-id-1
SPRINTHUB_PIPELINE_CURSO_2=pipeline-id-2

# Escalação
ESCALATION_WHATSAPP_NUMBER=5511999999999

# Cursos
COURSE_SLUGS=curso_1,curso_2
```

### 3️⃣ Suba os containers

```bash
docker-compose up -d
```

### 4️⃣ Verifique a saúde

```bash
curl http://localhost:8000/health
```

---

## 📱 Configurando o Webhook da Meta

### 1. Gere um token de verificação

```bash
echo "seu-token-super-secreto" > /tmp/verify_token.txt
cat /tmp/verify_token.txt
```

### 2. Configure o webhook no Meta App

Na configuração do seu app WhatsApp Business:

```
URL do Webhook: https://seu-dominio.com/webhook/whatsapp
Token de Verificação: <o-token-acima>
Webhook Fields: messages, message_status
```

### 3. Teste localmente com ngrok

```bash
ngrok http 8000
# Copie a URL https://abc123.ngrok.io
# Use https://abc123.ngrok.io/webhook/whatsapp no Meta App
```

---

## 📚 Configurando os Cursos

### 1. Atualize os nomes dos cursos

Edite `app/agents/courses/curso_1_agent.py` e `curso_2_agent.py`:

```python
system_prompt = """
Você é a Ana, consultora de [NOME DO CURSO 1]...
"""
```

### 2. Atualize a Knowledge Base

Edite `app/knowledge/courses/curso_1.md` e `curso_2.md` com as informações reais dos seus cursos:

```markdown
# Curso 1 — Pós-Graduação em [NOME]

## Investimento
- **Valor total:** R$ 15.000
- **Parcelamento:** 12x de R$ 1.500

## Diferenciais
- Professores com experiência de mercado
- Certificado reconhecido pelo MEC
- ...
```

### 3. Configure os pipelines do SprintHub

Obtenha os IDs dos pipelines no SprintHub e adicione ao `.env`:

```
SPRINTHUB_PIPELINE_CURSO_1=12345
SPRINTHUB_PIPELINE_CURSO_2=67890
```

---

## 🎙️ Configurando os Áudios do Script

### 1. Prepare seus áudios

Crie os arquivos de áudio (.mp3 ou .ogg) para cada passo do script:

```
audios/
├── curso_1/
│   ├── 01_boas_vindas.mp3
│   ├── 02_diferenciais.mp3
│   ├── 03_preco.mp3
│   ├── 04_depoimento.mp3
│   └── 05_cta_final.mp3
└── curso_2/
    ├── 01_boas_vindas.mp3
    ├── 02_mercado.mp3
    └── ...
```

### 2. Faça upload para a Meta

Use o script de upload:

```python
from app.services.whatsapp import upload_audio

media_id = await upload_audio("audios/curso_1/01_boas_vindas.mp3")
print(f"Media ID: {media_id}")
```

### 3. Atualize o script

Edite `app/script/schedules/curso_1_script.py` e `curso_2_script.py`:

```python
CURSO_1_SCRIPT = [
    {
        "delay_seconds": 2,
        "pre_text": "Oi! Que ótimo ter você aqui 🎉",
        "audio": "MEDIA_ID_RETORNADO_AQUI",  # <- Coloque o media_id aqui
        "post_text": "Ouviu? O que achou? 😊",
        "trigger": "auto",
    },
    # ... mais passos
]
```

---

## 🔄 Fluxo de uma Conversa

```
1. Lead manda "Oi" no WhatsApp
   ↓
2. Webhook recebe → cria sessão no Redis
   ↓
3. Router identifica: qual curso?
   ↓
4. Se novo lead → envia boas-vindas
   ↓
5. Lead responde mencionando um curso
   ↓
6. Agente especialista do curso ativa
   ↓
7. Claude responde com personalidade do consultor
   ↓
8. Script de áudios começa (passo 0)
   ↓
9. Após delay, próximo áudio dispara automaticamente
   ↓
10. Lead responde a algo → próximo passo do script por gatilho "response"
   ↓
11. Se lead tiver objeção → agente responde (não é nos áudios)
   ↓
12. Se lead pedir humano → escalação automática
   ↓
13. Histórico + estágio salvo no SprintHub
```

---

## 🛠️ Desenvolvimento Local

### Rodando sem Docker

```bash
# Instale as dependências
pip install -r requirements.txt

# Crie um .env com as variáveis
# (Redis e PostgreSQL rodando localmente ou docker-compose up)

# Rode a aplicação
uvicorn app.main:app --reload
```

### Testando o webhook localmente

```bash
# Terminal 1: Rodando a app
uvicorn app.main:app --reload

# Terminal 2: Usando ngrok
ngrok http 8000

# Terminal 3: Enviando mensagem de teste
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "object": "whatsapp_business_account",
    "entry": [{
      "id": "123",
      "changes": [{
        "value": {
          "messaging_product": "whatsapp",
          "metadata": {},
          "contacts": [{"profile": {"name": "João"}, "wa_id": "5511999999999"}],
          "messages": [{
            "from": "5511999999999",
            "id": "msg123",
            "timestamp": "1234567890",
            "type": "text",
            "text": {"body": "Oi, quero saber sobre o MBA"}
          }]
        },
        "field": "messages"
      }]
    }]
  }'
```

---

## 📊 Estrutura do Banco de Dados

### Tabela: `leads`
```sql
id          | INTEGER | PK
phone_number| STRING(20) | UNIQUE
name        | STRING(120)
course_slug | STRING(50)
stage       | STRING(30)  -- new, identifying, nurturing, objection, hot, negotiating, converted, escalated, lost
sprinthub_id| STRING(100)
script_step | INTEGER  -- qual passo do script está
is_escalated| BOOLEAN
notes       | TEXT
created_at  | DATETIME
updated_at  | DATETIME
```

### Tabela: `conversations`
```sql
id           | INTEGER | PK
phone_number | STRING(20)
role         | STRING(10)  -- "user" ou "assistant"
content      | TEXT
created_at   | DATETIME
```

### Tabela: `audio_logs`
```sql
id            | INTEGER | PK
phone_number  | STRING(20)
course_slug   | STRING(50)
script_step   | INTEGER
audio_filename| STRING(200)
sent_at       | DATETIME
```

---

## 🚨 Escalação para Humano

Quando um lead pede para falar com alguém:

1. **Agente detecta** palavras-chave ("falar com humano", "atendente", etc.)
2. **Lead é transferido** para estágio `ESCALATED`
3. **Aviso é enviado** para o número configurado em `ESCALATION_WHATSAPP_NUMBER`
4. **Script para** (não dispara mais áudios)
5. **SprintHub é atualizado** com o novo estágio

---

## 🐛 Troubleshooting

### Webhook não está recebendo mensagens

✅ Verifique o `META_VERIFY_TOKEN` está correto no .env
✅ Verifique que a URL está pública e acessível
✅ Cheque os logs: `docker-compose logs -f api`

### Áudios não estão sendo enviados

✅ Confirme que o `media_id` é válido (foi feito upload?)
✅ Verifique que o `META_ACCESS_TOKEN` está válido
✅ Cheque se o `delay_seconds` não está muito curto

### Claude não está respondendo

✅ Verifique `ANTHROPIC_API_KEY` está correto
✅ Cheque quota de tokens na sua conta Anthropic
✅ Veja os logs: `docker-compose logs -f api | grep Claude`

### Leads não aparecem no SprintHub

✅ Verifique `SPRINTHUB_API_KEY`
✅ Confirme que `SPRINTHUB_PIPELINE_CURSO_1` e `CURSO_2` estão corretos
✅ Cheque se a API do SprintHub está online

---

## 📈 Monitoramento em Produção

### Logs estruturados

Todos os eventos importantes são logados:

```
🚀 Sales Agent iniciando...
✅ Conexões estabelecidas com sucesso.
📥 Nova mensagem recebida. phone=5511999999999 type=text
🔀 Curso identificado pelo router. course=curso_1
🤖 Agente respondeu. stage=nurturing
🔊 Passo do script executado. step=0
🚨 Escalando lead para humano.
✅ Lead criado no SprintHub.
```

### Health check

```bash
curl http://seu-dominio.com/health
```

Retorna:
```json
{"status": "ok", "env": "production"}
```

---

## 🔐 Segurança

- ✅ Variáveis sensíveis em `.env` (nunca commit!)
- ✅ Redis com TLS em produção
- ✅ PostgreSQL com senha forte
- ✅ Validação de webhook token
- ✅ Rate limiting recomendado (configure no nginx/proxy)
- ✅ HTTPS obrigatório para webhook

---

## 📦 Deploy na Hostinger VPS

### 1. Acesse via SSH

```bash
ssh root@seu-vps-ip
```

### 2. Instale Docker

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker root
```

### 3. Clone o repositório

```bash
git clone <seu-repo> /opt/sales-agent
cd /opt/sales-agent
```

### 4. Configure o `.env`

```bash
nano .env
# Preench com valores reais
```

### 5. Suba com Docker Compose

```bash
docker-compose -f docker-compose.yml up -d
```

### 6. Configure Nginx (reverse proxy)

```nginx
server {
    listen 80;
    server_name seu-dominio.com;
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 7. SSL com Certbot

```bash
apt install certbot python3-certbot-nginx
certbot --nginx -d seu-dominio.com
```

---

## 📞 Suporte

- Dúvidas? Verifique os logs: `docker-compose logs -f api`
- Erro de API? Cheque as credenciais no `.env`
- Agente não responde? Reinicie: `docker-compose restart api`

---

## 📝 Próximos Passos

1. ✅ Configure seus 2 cursos
2. ✅ Crie os arquivos de áudio (.mp3/.ogg)
3. ✅ Atualize as knowledge bases (.md)
4. ✅ Configure as APIs (Meta, SprintHub, Anthropic)
5. ✅ Faça upload dos áudios para a Meta
6. ✅ Teste localmente com ngrok
7. ✅ Deploy na Hostinger VPS
8. ✅ Configure o webhook no Meta App
9. ✅ Teste com leads reais
10. ✅ Monitore e otimize os agentes

---

**Boa sorte com sua Sales Agent! 🚀🎉**
