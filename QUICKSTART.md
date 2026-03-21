# ⚡ Quick Start — 10 Minutos

Comece com o Sales Agent em 10 minutos!

---

## ✅ Requisito de versão Python

Use **Python 3.11** para execução local dos scripts/pytest.
(Com Docker, o container já usa 3.11.)

---

## 1️⃣ Clone o Repositório

```bash
git clone <seu-repo>
cd sales-agent
```

---

## 2️⃣ Configure o `.env`

```bash
cp env.example .env
```

Preencha os valores críticos no `.env`:

```env
# Obtenha no Meta App
META_VERIFY_TOKEN=seu-token-aleatorio
META_ACCESS_TOKEN=seu-token-permanente
META_PHONE_NUMBER_ID=seu-phone-number-id

# Obtenha em console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-...

# Obtenha no SprintHub
SPRINTHUB_API_KEY=sua-chave

# Senhas (pode ser aleatório para dev local)
POSTGRES_PASSWORD=senha123
```

---

## 3️⃣ Suba os Containers

```bash
docker-compose up -d
```

Verifique:

```bash
docker-compose ps
# Todos devem estar "Up"
```

---

## 4️⃣ Teste a API

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{"status": "ok", "env": "development"}
```

---

## 5️⃣ Teste o Webhook

Terminal 1 — Se quiser testar com ngrok:

```bash
ngrok http 8000
# Copie a URL gerada (ex: https://abc123.ngrok.io)
```

Terminal 2 — Envie uma mensagem de teste:

```bash
bash test_webhook.sh http://localhost:8000 5511999999999
```

---

## 6️⃣ Verifique os Logs

```bash
docker-compose logs -f api
```

Você deve ver:

```
📥 Nova mensagem recebida. phone=5511999999999 type=text
🤖 Agente respondeu.
✅ Lead criado no Redis.
```

---

## 7️⃣ Configure seus Cursos

Edite os nomes dos cursos:

**`app/agents/courses/curso_1_agent.py`:**

```python
system_prompt = """
Você é a Ana, consultora de [NOME DO SEU CURSO 1]...
"""
```

**`app/agents/courses/curso_2_agent.py`:**

```python
system_prompt = """
Você é o Carlos, consultor de [NOME DO SEU CURSO 2]...
"""
```

---

## 8️⃣ Atualize a Knowledge Base

**`app/knowledge/courses/curso_1.md`:**

```markdown
# Curso 1 — [Seu Nome]

## Investimento
- Valor: R$ X
- Parcelamento: Xx de R$ Y

## Diferenciais
- [Seu diferencial 1]
- [Seu diferencial 2]
...
```

Faça o mesmo em `curso_2.md`.

---

## 9️⃣ Teste os Agentes

```bash
python3.11 scripts/test_agents.py
```

Você vai ver uma conversa simulada com cada agente.

---

## 🔟 Está Pronto!

Agora você pode:

✅ Testar localmente com ngrok
✅ Fazer deploy na VPS
✅ Configurar webhook no Meta
✅ Receber leads reais

---

## 📚 Próximos Passos

1. **Gravar áudios** → `SETUP_AUDIOS.md`
2. **Fazer upload** → `python3.11 scripts/upload_audios.py`
3. **Personalizar agentes** → `AGENT_TRAINING.md`
4. **Deploy em produção** → `DEPLOYMENT.md`
5. **Checklist final** → `PREPRODUCTION_CHECKLIST.md`

---

## 🆘 Algo Errado?

Verifique os logs:

```bash
docker-compose logs -f api
```

Ou veja a seção de Troubleshooting em `FAQ.md`.

---

**Pronto! Sua Sales Agent está rodando! 🚀**
