# 📚 Índice Completo — Sales Agent

Guia de navegação por toda a documentação do projeto.

---

## 🚀 Comece Por Aqui

1. **[QUICKSTART.md](QUICKSTART.md)** ⚡ — 10 minutos para tudo funcionar
2. **[FIRST_RUN.md](FIRST_RUN.md)** 🎬 — Seu primeiro teste passo a passo
3. **[README.md](README.md)** 📖 — Documentação completa

---

## 📋 Guias Principais

### Setup e Configuração
- **[QUICKSTART.md](QUICKSTART.md)** — Comece aqui (10 min)
- **[FIRST_RUN.md](FIRST_RUN.md)** — Teste local com passo a passo
- **[env.example](env.example)** — Modelo de variáveis de ambiente

### Customização e Treinamento
- **[AGENT_TRAINING.md](AGENT_TRAINING.md)** — Treinar agentes para parecerem humanos
- **[SETUP_AUDIOS.md](SETUP_AUDIOS.md)** — Gravar, fazer upload e configurar áudios
- **[STRUCTURE.md](STRUCTURE.md)** — Estrutura completa do projeto

### Deployment
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — Deploy na Hostinger VPS
- **[PREPRODUCTION_CHECKLIST.md](PREPRODUCTION_CHECKLIST.md)** — Checklist antes de ir ao vivo

### Referência
- **[FAQ.md](FAQ.md)** — Perguntas frequentes e troubleshooting
- **[README.md](README.md)** — Documentação técnica completa

---

## 🎯 Por Objetivo

### "Quero testar agora"
→ [QUICKSTART.md](QUICKSTART.md) → [FIRST_RUN.md](FIRST_RUN.md)

### "Quero personalizar os agentes"
→ [AGENT_TRAINING.md](AGENT_TRAINING.md) → edite `app/agents/courses/`

### "Quero configurar áudios"
→ [SETUP_AUDIOS.md](SETUP_AUDIOS.md) → `python scripts/upload_audios.py`

### "Quero fazer deploy"
→ [DEPLOYMENT.md](DEPLOYMENT.md) → [PREPRODUCTION_CHECKLIST.md](PREPRODUCTION_CHECKLIST.md)

### "Estou com erro"
→ [FAQ.md](FAQ.md) → procure sua dúvida

### "Quero entender a estrutura"
→ [STRUCTURE.md](STRUCTURE.md) → [README.md](README.md)

---

## 📁 Arquivos Importantes

### Configuração
```
env.example              # Modelo de .env (copie para .env)
docker-compose.yml      # Orquestração de containers
Dockerfile              # Imagem da aplicação
requirements.txt        # Dependências Python
Makefile               # Atalhos de comandos
```

### Código-fonte
```
app/main.py                          # Entry point FastAPI
app/config.py                        # Pydantic Settings
app/api/webhooks.py                  # POST /webhook/whatsapp
app/agents/                          # Agentes de IA
app/agents/courses/curso_1_agent.py # Agente Curso 1 (EDITE!)
app/agents/courses/curso_2_agent.py # Agente Curso 2 (EDITE!)
app/knowledge/courses/               # Base de conhecimento
app/knowledge/courses/curso_1.md    # Info Curso 1 (EDITE!)
app/knowledge/courses/curso_2.md    # Info Curso 2 (EDITE!)
app/script/schedules/                # Scripts de áudios
app/script/schedules/curso_1_script.py # Script Curso 1 (EDITE!)
app/script/schedules/curso_2_script.py # Script Curso 2 (EDITE!)
```

### Testes e Utilitários
```
test_webhook.sh           # Script para testar webhook
example.http             # Exemplos de requisições HTTP
scripts/upload_audios.py # Upload de áudios para Meta
scripts/test_agents.py   # Testa agentes localmente
scripts/generate_report.py # Gera relatório de vendas
Makefile                 # Atalhos úteis
```

### Documentação
```
README.md                       # Documentação principal
QUICKSTART.md                   # Início rápido
FIRST_RUN.md                    # Primeiro teste
AGENT_TRAINING.md               # Treinar agentes
SETUP_AUDIOS.md                 # Configurar áudios
DEPLOYMENT.md                   # Deploy em produção
PREPRODUCTION_CHECKLIST.md      # Checklist pré-produção
STRUCTURE.md                    # Estrutura do projeto
FAQ.md                          # Perguntas frequentes
INDEX.md                        # Este arquivo
```

---

## 🔄 Fluxo Típico de Desenvolvimento

```
1. Clone o repositório
   ↓
2. Siga QUICKSTART.md (10 min)
   ↓
3. Siga FIRST_RUN.md (teste local)
   ↓
4. Edite os agentes (AGENT_TRAINING.md)
   ↓
5. Configure os cursos (knowledge base .md)
   ↓
6. Configure os áudios (SETUP_AUDIOS.md)
   ↓
7. Faça o checklist (PREPRODUCTION_CHECKLIST.md)
   ↓
8. Deploy (DEPLOYMENT.md)
   ↓
9. Configure webhook (README.md seção "Webhook")
   ↓
10. Envie para leads reais!
```

---

## 🆘 Troubleshooting Rápido

| Problema | Solução |
|----------|---------|
| API não inicia | Verifique `.env` e veja `docker-compose logs api` |
| Webhook não funciona | Veja [FAQ.md](FAQ.md) seção "Webhook" |
| Agente não responde | Verifique `ANTHROPIC_API_KEY` em [FAQ.md](FAQ.md) |
| Áudios não enviam | Veja [SETUP_AUDIOS.md](SETUP_AUDIOS.md) troubleshooting |
| Deploy falha | Siga [DEPLOYMENT.md](DEPLOYMENT.md) passo a passo |
| Outro erro | Procure em [FAQ.md](FAQ.md) ou abra uma issue |

---

## 📊 Stack Tecnológico

```
Backend:       FastAPI (Python 3.11+)
IA:            Anthropic Claude Sonnet
Cache:         Redis
Banco:         PostgreSQL
WhatsApp:      Meta API Oficial
CRM:           SprintHub
Deploy:        Docker + VPS (Hostinger)
SSL:           Let's Encrypt + Nginx
```

---

## 🎓 Aprendizado Progressivo

### Nível 1 — Iniciante
Leia em ordem:
1. QUICKSTART.md
2. FIRST_RUN.md
3. README.md (seção "Fluxo")

### Nível 2 — Intermediário
1. AGENT_TRAINING.md
2. SETUP_AUDIOS.md
3. STRUCTURE.md

### Nível 3 — Avançado
1. DEPLOYMENT.md
2. README.md (seções técnicas)
3. Código-fonte em `app/`

---

## 🛠️ Comandos Rápidos

```bash
# Setup
make setup              # Setup inicial
make up                 # Inicia containers
make down               # Para containers

# Testes
make test              # Roda testes
make test-webhook      # Testa webhook
make test-agents       # Testa agentes

# Utilidades
make logs              # Vê logs
make shell-api         # Entra no shell da API
make backup-db         # Faz backup do banco
make clean             # Remove tudo
```

Veja `Makefile` para mais comandos.

---

## 🌐 Recursos Externos

- **Meta Developers:** https://developers.facebook.com/
- **Anthropic Console:** https://console.anthropic.com/
- **SprintHub:** https://www.sprinthub.com.br/
- **Docker:** https://docker.com/
- **FastAPI:** https://fastapi.tiangolo.com/
- **PostgreSQL:** https://www.postgresql.org/
- **Redis:** https://redis.io/

---

## 📞 Suporte

### Se tiver dúvida
1. Procure em [FAQ.md](FAQ.md)
2. Verifique os logs: `docker-compose logs -f api`
3. Leia o README.md seção relevante
4. Abra uma issue no GitHub

### Se tiver bug
1. Descreva o problema
2. Inclua os logs completos
3. Diga como reproduzir
4. Que versão do Python/Docker você usa

---

## ✅ Checklist de Navegação

Use este índice para:

- [ ] Encontrar a documentação que precisa
- [ ] Entender a estrutura do projeto
- [ ] Navegar pelos guias na ordem certa
- [ ] Resolver problemas rapidamente
- [ ] Aprender progressivamente

---

## 📝 Resumo dos Arquivos

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| README.md | 📖 Docs | Documentação completa |
| QUICKSTART.md | ⚡ Docs | Comece em 10 min |
| FIRST_RUN.md | 🎬 Docs | Primeiro teste |
| AGENT_TRAINING.md | 🧠 Docs | Treinar agentes |
| SETUP_AUDIOS.md | 🎙️ Docs | Áudios e upload |
| DEPLOYMENT.md | 🚀 Docs | Deploy em produção |
| PREPRODUCTION_CHECKLIST.md | ✅ Docs | Checklist pré-prod |
| STRUCTURE.md | 📁 Docs | Estrutura do projeto |
| FAQ.md | ❓ Docs | Perguntas frequentes |
| INDEX.md | 📚 Docs | Este arquivo |
| docker-compose.yml | ⚙️ Config | Containers |
| Dockerfile | 🐳 Config | Imagem Docker |
| requirements.txt | 📦 Config | Dependências |
| env.example | 🔐 Config | Variáveis modelo |
| Makefile | 🛠️ Config | Atalhos |
| test_webhook.sh | 🧪 Script | Teste webhook |
| example.http | 💻 Exemplo | Requisições HTTP |
| app/ | 💻 Código | Aplicação |
| scripts/ | 🛠️ Código | Utilitários |
| tests/ | 🧪 Código | Testes |

---

**Bem-vindo ao Sales Agent! Escolha um ponto de partida acima e comece! 🚀**
