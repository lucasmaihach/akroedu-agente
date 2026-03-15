# ❓ FAQ — Perguntas Frequentes

Respostas para as dúvidas mais comuns sobre o Sales Agent.

---

## 🚀 Setup e Instalação

### P: Como faço o primeiro setup?

**R:** Siga estes passos:

```bash
git clone <seu-repo>
cd sales-agent
cp env.example .env
nano .env  # Edite com suas credenciais
docker-compose up -d
```

Verifique: `curl http://localhost:8000/health`

---

### P: O `.env` está correto mas a API não inicia. O que fazer?

**R:** Verifique os logs:

```bash
docker-compose logs -f api
```

Erros comuns:
- ❌ `ANTHROPIC_API_KEY` inválido → gera erro de autenticação
- ❌ `DATABASE_URL` errado → falha ao conectar no PostgreSQL
- ❌ `REDIS_URL` inválido → Redis não conecta

Regenere os valores e tente novamente.

---

### P: Redis ou PostgreSQL não iniciam. Como resetar?

**R:** Remove tudo e começa do zero:

```bash
docker-compose down -v  # Remove containers E volumes
docker-compose up -d    # Cria novos containers
```

**Aviso:** Isso deleta TODOS os dados (conversas, leads, etc.). Use em desenvolvimento!

---

## 🤖 Agentes e IA

### P: O agente está respondendo de forma muito robótica. Como humanizar?

**R:** Edite o `system_prompt` do agente:

1. Dê um nome e profissão ("Sou a Ana, consultora...")
2. Adicione maneirismos ("né", "tipo assim", "sabe")
3. Inclua emojis naturalmente (máx 2 por mensagem)
4. Use mais perguntas que afirmações
5. Conte histórias/depoimentos, não só venda

Veja o guia: `AGENT_TRAINING.md`

---

### P: Como faço o agente responder perguntas específicas do meu curso?

**R:** Atualize a knowledge base:

1. Edite `app/knowledge/courses/curso_1.md`
2. Adicione seções completas (Diferenciais, Investimento, Objeções)
3. Salve e reinicie:

```bash
docker-compose restart api
```

O agente automaticamente carrega a info atualizada.

---

### P: Estou usando Groq (IA gratuita) em vez de OpenAI. Funciona?

**R:** Sim! O projeto usa Anthropic (Claude), não OpenAI. Para usar Groq:

1. Altere `ANTHROPIC_API_KEY` para sua chave Groq
2. Mude `ANTHROPIC_MODEL` para `mixtral-8x7b-32768`
3. Adapte o `system_prompt` se necessário

**Cuidado:** Groq pode ter latência maior e respostas menos consistentes.

---

## 🎙️ Áudios do Script

### P: Como faço upload dos áudios?

**R:** Execute o script de upload:

```bash
python scripts/upload_audios.py
```

Ele:
1. Lê todos os arquivos em `audios/`
2. Faz upload para a Meta
3. Salva os media_ids em `audio_media_ids.json`

---

### P: Qual é o tamanho máximo do áudio?

**R:** Meta API aceita até **100 MB por arquivo**, mas recomenda **16 MB máximo** para evitar timeouts.

**Dica:** Comprima seus áudios em 128 kbps MP3 ou OGG.

---

### P: Os áudios não estão sendo enviados. O que fazer?

**R:** Checklist:

- [ ] Media ID está correto no script? (`app/script/schedules/curso_1_script.py`)
- [ ] O áudio foi realmente feito upload? (check em `audio_media_ids.json`)
- [ ] `META_ACCESS_TOKEN` é válido?
- [ ] Os delays estão muito curtos?

Verifique logs:
```bash
docker-compose logs -f api | grep -i audio
```

---

### P: Preciso atualizar um áudio. Como faço?

**R:** 
1. Gravação novo áudio
2. Substitua o arquivo em `audios/curso_1/01_boas_vindas.mp3`
3. Execute upload novamente:
   ```bash
   python scripts/upload_audios.py
   ```
4. Copie o novo media_id
5. Atualize `app/script/schedules/curso_1_script.py`
6. Reinicie: `docker-compose restart api`

---

## 📱 WhatsApp e Webhook

### P: Como testo o webhook localmente?

**R:** Use ngrok:

```bash
# Terminal 1: API rodando
docker-compose up -d

# Terminal 2: ngrok expõe a porta
ngrok http 8000

# Terminal 3: Configure no Meta App
# URL: https://abc123.ngrok.io/webhook/whatsapp
# Token: seu-token

# Terminal 4: Teste
./test_webhook.sh https://abc123.ngrok.io 5511999999999
```

---

### P: O webhook retorna 200 mas a mensagem não é processada. Por quê?

**R:** O webhook retorna 200 imediatamente, mas processa em background.

Verifique:
1. Logs da API: `docker-compose logs -f api | grep "📥"`
2. Webhook foi registrado corretamente no Meta?
3. Token de verificação está certo?

---

### P: Lead manda mensagem, mas agente não responde. O que fazer?

**R:** Debug steps:

1. Verifique se o lead foi criado no Redis:
   ```bash
   docker-compose exec redis redis-cli KEYS "lead:*"
   ```

2. Verifique histórico:
   ```bash
   docker-compose exec redis redis-cli LRANGE "history:5511999999999" 0 -1
   ```

3. Verifique logs da API:
   ```bash
   docker-compose logs -f api | grep "phone-do-lead"
   ```

4. É um erro de Claude? Verifique quota de API

---

### P: Agente responde, mas o lead não recebe. Por quê?

**R:** Possível causa: Token da Meta expirou ou está inválido.

Solução:
1. Gere um novo `META_ACCESS_TOKEN` no Meta App
2. Atualize no `.env`
3. Reinicie: `docker-compose restart api`

---

## 💾 Banco de Dados e Dados

### P: Quantos leads posso armazenar?

**R:** PostgreSQL padrão: **ilimitado** (depende da capacidade da VPS).

**Recomendação:** Limpe conversas antigas a cada 30 dias:

```bash
docker-compose exec postgres psql -U sales_agent -d sales_agent_db \
  -c "DELETE FROM conversations WHERE created_at < NOW() - INTERVAL '30 days';"
```

---

### P: Como faço backup dos dados?

**R:** Use o Makefile:

```bash
make backup-db
```

Ou manualmente:

```bash
docker exec sales_agent_postgres pg_dump -U sales_agent sales_agent_db > backup.sql
```

Para restaurar:

```bash
cat backup.sql | docker exec -i sales_agent_postgres psql -U sales_agent sales_agent_db
```

---

### P: Preciso acessar o banco para fazer query custom. Como?

**R:** Entre no psql:

```bash
docker-compose exec postgres psql -U sales_agent -d sales_agent_db
```

Exemplos:

```sql
-- Ver todos os leads
SELECT phone_number, name, stage, course_slug FROM leads;

-- Ver conversas de um lead
SELECT role, content FROM conversations WHERE phone_number = '5511999999999';

-- Contar leads por estágio
SELECT stage, COUNT(*) FROM leads GROUP BY stage;
```

---

## 🔧 Integração SprintHub

### P: Leads não estão sendo salvos no SprintHub. Por quê?

**R:** Checklist:

- [ ] `SPRINTHUB_API_KEY` está correto?
- [ ] `SPRINTHUB_PIPELINE_CURSO_1` e `CURSO_2` estão corretos?
- [ ] Os pipelines existem no SprintHub?

Verifique logs:
```bash
docker-compose logs -f api | grep -i sprinthub
```

---

### P: Como sincronizo leads antigos com o SprintHub?

**R:** Crie um script temporário:

```python
from app.db.database import AsyncSessionLocal
from app.db.orm_models import LeadORM
from app.services.crm import sync_lead
from app.models.lead import Lead

async def sync_all():
    async with AsyncSessionLocal() as session:
        leads = await session.execute(select(LeadORM))
        for lead_orm in leads.scalars():
            lead = Lead(
                phone_number=lead_orm.phone_number,
                name=lead_orm.name,
                course_slug=lead_orm.course_slug,
                stage=lead_orm.stage,
            )
            await sync_lead(lead)
```

---

## 📊 Relatórios e Métricas

### P: Como gero um relatório de vendas?

**R:** Use o script:

```bash
# Texto
python scripts/generate_report.py

# JSON
python scripts/generate_report.py --format json

# HTML
python scripts/generate_report.py --format html

# Últimos 30 dias
python scripts/generate_report.py --days 30
```

---

### P: Qual é a taxa de conversão esperada?

**R:** Varia muito, mas:

- **B2B educação**: 5-15% é bom
- **Cold leads**: 1-5%
- **Warm leads** (já interessados): 20-40%

Acompanhe via SprintHub e otimize os agentes conforme aprende.

---

## 🚀 Deployment e Produção

### P: Como faço deploy na Hostinger?

**R:** Veja o guia completo: `DEPLOYMENT.md`

Resumo:
1. SSH na VPS
2. `git clone` seu repo
3. Edite `.env`
4. `docker-compose up -d`
5. Configure Nginx + SSL
6. Registre webhook no Meta

---

### P: A aplicação está lenta em produção. Como otimizar?

**R:** Dicas:

1. **Aumentar workers:**
   ```bash
   # No docker-compose.yml
   command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

2. **Redis caching agressivo:** Ajuste `SESSION_TTL_HOURS`

3. **PostgreSQL índices:**
   ```sql
   CREATE INDEX idx_phone_number ON leads(phone_number);
   CREATE INDEX idx_created_at ON conversations(created_at);
   ```

4. **Monitorar:**
   ```bash
   docker stats
   ```

---

### P: SSL/HTTPS não está funcionando. Como debugar?

**R:**

```bash
# Verifique certificado
certbot certificates

# Renew manual
certbot renew --force-renewal

# Verifique Nginx
nginx -t
systemctl restart nginx

# Teste acesso
curl -v https://seu-dominio.com/health
```

---

## 🐛 Erros Comuns

### P: "ConnectionRefusedError: Redis connection failed"

**R:** Redis não está rodando:

```bash
docker-compose ps
docker-compose restart redis
docker-compose logs redis
```

---

### P: "OperationalError: could not translate host name 'postgres'"

**R:** PostgreSQL não está rodando ou rede Docker errada:

```bash
docker-compose restart postgres
docker network ls
docker-compose down && docker-compose up -d
```

---

### P: "timeout exceeded" em requisições Meta

**R:** Meta API está lenta ou IP da VPS foi bloqueado:

1. Tente fazer a requisição manual:
   ```bash
   curl "https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages" \
     -H "Authorization: Bearer {TOKEN}"
   ```

2. Se falhar, token expirou ou IP bloqueado
3. Regenere token no Meta App ou entre em contato com suporte

---

## 📞 Suporte e Comunidade

### P: Encontrei um bug. Como reportar?

**R:** Crie uma issue no GitHub com:
1. Versão do código
2. Logs de erro completos
3. Passos para reproduzir
4. Seu OS e versão Python

---

### P: Preciso de customizações. Quem contrata?

**R:** Entre em contato com o time de desenvolvimento via GitHub Issues ou e-mail.

---

**Não encontrou sua pergunta?**

Verifique:
- `README.md` — documentação geral
- `DEPLOYMENT.md` — guia de deploy
- `AGENT_TRAINING.md` — personalização de agentes
- `SETUP_AUDIOS.md` — configuração de áudios

Ou abra uma issue no GitHub! 🚀
