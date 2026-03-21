# 🎬 First Run — Seu Primeiro Teste

Parabéns! Você clonou o projeto. Agora vamos fazer funcionar em 5 minutos.

---

## ✅ Pré-requisitos

- [ ] Python 3.11 instalado (`python3.11 --version`) para rodar scripts locais
- [ ] Docker instalado (`docker --version`)
- [ ] Docker Compose instalado (`docker-compose --version`)
- [ ] Git clonado
- [ ] Arquivo `.env` com credenciais (veja abaixo)

---

## 🔐 Conseguir as Credenciais

### Meta WhatsApp API
1. Acesse https://developers.facebook.com/
2. Crie uma App (WhatsApp)
3. Vá em "WhatsApp Business" → "Configuração"
4. Copie:
   - `META_PHONE_NUMBER_ID`
   - `META_ACCESS_TOKEN` (crie um permanente)
5. Gere um token aleatório para `META_VERIFY_TOKEN`:
   ```bash
   openssl rand -hex 32
   ```

### Anthropic Claude
1. Acesse https://console.anthropic.com/
2. Crie uma conta
3. Vá em "API Keys"
4. Crie uma nova chave
5. Copie como `ANTHROPIC_API_KEY`

### SprintHub (Opcional para teste)
1. Se tiver conta, obtenha `SPRINTHUB_API_KEY`
2. Crie 3 pipelines: `curso_1`, `curso_2` e `pos_fisio_neuro`
3. Copie os IDs dos pipelines

---

## 🚀 Passo 1: Crie o `.env`

```bash
cp env.example .env
nano .env
```

Preencha os valores:

```env
APP_ENV=development
APP_SECRET=dev-secret-teste

# Meta
META_VERIFY_TOKEN=abc123def456...
META_ACCESS_TOKEN=EAABs...
META_PHONE_NUMBER_ID=123456789
META_API_VERSION=v20.0

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5

# Redis (deixe padrão)
REDIS_URL=redis://redis:6379/0
SESSION_TTL_HOURS=48

# PostgreSQL (deixe padrão para dev)
POSTGRES_USER=sales_agent
POSTGRES_PASSWORD=dev123
POSTGRES_DB=sales_agent_db
DATABASE_URL=postgresql+asyncpg://sales_agent:dev123@postgres:5432/sales_agent_db

# SprintHub (deixe vazio se não tiver)
SPRINTHUB_API_URL=https://api.sprinthub.com.br
SPRINTHUB_API_KEY=sua-chave-ou-vazio
SPRINTHUB_PIPELINE_CURSO_1=id-ou-vazio
SPRINTHUB_PIPELINE_CURSO_2=id-ou-vazio
SPRINTHUB_PIPELINE_POS_FISIO_NEURO=id-ou-vazio

# Escalação (seu número WhatsApp)
ESCALATION_WHATSAPP_NUMBER=5511999999999

# Cursos
COURSE_SLUGS=curso_1,curso_2,pos_fisio_neuro
```

---

## 🚀 Passo 2: Suba os Containers

```bash
docker-compose up -d
```

Aguarde 10-15 segundos para o banco iniciar.

Verifique:

```bash
docker-compose ps
```

Você deve ver 3 containers "Up":
- `sales_agent_api`
- `sales_agent_postgres`
- `sales_agent_redis`

---

## 🚀 Passo 3: Teste a API

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{"status":"ok","env":"development"}
```

✅ **Se chegou aqui, a API está rodando!**

---

## 🚀 Passo 4: Teste o Webhook Localmente

**Terminal 1** — Veja os logs em tempo real:

```bash
docker-compose logs -f api
```

**Terminal 2** — Envie uma mensagem de teste:

```bash
bash test_webhook.sh http://localhost:8000 5511987654321
```

**Esperado nos logs:**

```
📥 Nova mensagem recebida. phone=5511987654321 type=text
🔀 Curso identificado pelo router. course=unknown
🤖 Agente respondeu.
```

✅ **Se viu as mensagens, o webhook funciona!**

---

## 🚀 Passo 5: Teste o Agente

```bash
python3.11 scripts/test_agents.py
```

Você vai ver uma conversa simulada com cada agente:

```
======================================================================
🧪 Testando Agente: Curso 1
======================================================================

👤 Lead [1]: Oi, tudo bem? Quanto custa o curso?
🤖 Agente: Oi! Tudo bem sim! Que legal você ter interesse... [resposta do Claude]

👤 Lead [2]: Tem desconto se pagar à vista?
🤖 Agente: Sim, temos condição especial para pagamento à vista...
```

✅ **Se saiu texto do Claude, os agentes funcionam!**

---

## 🎙️ Passo 6: Upload de Áudios (Opcional)

Se tiver áudios gravados:

```bash
# Organize em:
mkdir -p audios/curso_1 audios/curso_2 audios/pos_fisio_neuro
# Coloque os .mp3 nas pastas

# Faça upload
python3.11 scripts/upload_audios.py
```

Vai retornar media IDs. Copie e cole em:
- `app/script/schedules/curso_1_script.py`
- `app/script/schedules/curso_2_script.py`
- `app/script/schedules/pos_fisio_neuro_script.py`

---

## 🌐 Passo 7: Teste com ngrok (Opcional)

Se quer testar webhook com WhatsApp real:

**Terminal 3** — Exponha a porta:

```bash
ngrok http 8000
```

Vai gerar uma URL como: `https://abc123.ngrok.io`

No Meta App, configure webhook:
- URL: `https://abc123.ngrok.io/webhook/whatsapp`
- Token: seu `META_VERIFY_TOKEN`

Clique em "Verificar e Salvar".

Mande uma mensagem no WhatsApp para o número configurado.

---

## 📊 Passo 8: Verifique os Dados

Acesse o PostgreSQL:

```bash
docker-compose exec postgres psql -U sales_agent -d sales_agent_db
```

Veja os leads criados:

```sql
SELECT phone_number, name, stage, course_slug FROM leads;
```

Saia com `\q`.

---

## 🎉 Pronto!

Você tem agora:

✅ API rodando e respondendo
✅ Webhook funcionando
✅ Agentes testados
✅ Banco de dados persistindo dados
✅ Redis cacheando sessões

---

## 📝 Próximos Passos

1. **Personalizar agentes:**
   - Edite `app/agents/courses/curso_1_agent.py`
   - Edite `app/agents/courses/curso_2_agent.py`

2. **Atualizar knowledge base:**
   - Edite `app/knowledge/courses/curso_1.md`
   - Edite `app/knowledge/courses/curso_2.md`

3. **Gravar e configurar áudios:**
   - Veja `SETUP_AUDIOS.md`

4. **Deploy em produção:**
   - Veja `DEPLOYMENT.md`

5. **Checklist final:**
   - Veja `PREPRODUCTION_CHECKLIST.md`

---

## 🆘 Algo Errado?

### "Containers não iniciam"

```bash
docker-compose logs api
docker-compose logs postgres
```

### "API retorna 500"

Verifique `.env` — alguma credencial inválida?

```bash
docker-compose down
# Edite .env
docker-compose up -d
```

### "Claude não responde"

Verifique `ANTHROPIC_API_KEY`:

```bash
curl -H "Authorization: Bearer $ANTHROPIC_API_KEY" \
  https://api.anthropic.com/v1/messages
```

### "Webhook não recebe mensagens"

Verifique:
1. Token de verificação está correto no Meta?
2. URL está pública (ngrok ou domínio)?
3. Webhook foi registrado?

Veja logs:
```bash
docker-compose logs -f api | grep webhook
```

---

## ✅ Checklist de Primeiro Run

- [ ] Docker Compose up executado
- [ ] 3 containers rodando
- [ ] Curl /health retorna 200
- [ ] Test webhook funcionou
- [ ] Test agents rodou sem erro
- [ ] PostgreSQL acessível
- [ ] Redis respondendo
- [ ] `.env` preenchido corretamente
- [ ] Mensagens de teste salvaram no banco

---

**Parabéns! Seu Sales Agent está pronto para desenvolvimento! 🎉**

Próxima parada: personalize os agentes e configure seus cursos!
