# 🔧 Guia de Troubleshooting Detalhado

Soluções para problemas comuns, com passos específicos e logs esperados.

---

## 🔴 Problema: API não inicia

### Sintomas
```bash
$ docker-compose up -d
ERROR: service 'api' failed to start
```

### Diagnóstico

**Passo 1:** Verifique os logs

```bash
docker-compose logs api
```

Procure por uma das mensagens abaixo.

---

### ❌ Erro: "ANTHROPIC_API_KEY is not set"

**Causa:** Variável `.env` não preenchida

**Solução:**

```bash
nano .env
# Procure por: ANTHROPIC_API_KEY=sk-ant-...
# Se estiver vazio, gere em console.anthropic.com
```

**Teste:**

```bash
echo $ANTHROPIC_API_KEY
# Deve retornar sua chave
```

---

### ❌ Erro: "could not translate host name 'postgres'"

**Causa:** PostgreSQL não está rodando ou rede Docker errada

**Solução:**

```bash
# Verifique se postgres está up
docker-compose ps

# Se não estiver:
docker-compose restart postgres
docker-compose logs postgres

# Aguarde 5 segundos e tente novamente
sleep 5
docker-compose up -d api
```

**Esperado nos logs do postgres:**

```
PostgreSQL init process complete; ready for start up.
database system is ready to accept connections
```

---

### ❌ Erro: "Address already in use :8000"

**Causa:** Outra aplicação usando porta 8000

**Solução:**

**Opção A:** Mude a porta no `docker-compose.yml`

```yaml
api:
  ports:
    - "8001:8000"  # Porta externa muda de 8000 para 8001
```

**Opção B:** Mata o processo na porta 8000

```bash
# macOS/Linux
lsof -ti:8000 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

---

### ❌ Erro: "ModuleNotFoundError: No module named 'anthropic'"

**Causa:** Dependências Python não instaladas

**Solução:**

```bash
# Reconstrói a imagem Docker com dependências novas
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## 🔴 Problema: Webhook não recebe mensagens

### Sintomas
- Lead manda mensagem no WhatsApp
- API não recebe nada
- Nenhuma mensagem nos logs

### Diagnóstico

**Passo 1:** Verifique se webhook está registrado

1. Acesse https://developers.facebook.com/
2. Vá em sua App → WhatsApp → Configuração
3. Verifique que "Webhooks" está lá
4. URL deve ser: `https://seu-dominio.com/webhook/whatsapp` (em produção)
5. Token de verificação deve ser o do seu `.env`

**Passo 2:** Teste a verificação do webhook

```bash
# Localmente:
curl "http://localhost:8000/webhook/whatsapp?hub.verify_token=seu-token&hub.challenge=123"

# Esperado:
# 123
```

**Passo 3:** Teste POST no webhook

```bash
bash test_webhook.sh http://localhost:8000 5511999999999
```

---

### ❌ "Webhook retorna 404"

**Causa:** URL está errada ou API não está rodando

**Solução:**

```bash
# Verifique se API está up
curl http://seu-dominio.com/health

# Se retorna erro, API não está rodando
docker-compose logs api

# Se URL está local (localhost), não vai funcionar com WhatsApp real
# Use ngrok para expor localmente:
ngrok http 8000
# Copie a URL gerada
```

---

### ❌ "Webhook retorna 403 Forbidden"

**Causa:** Token de verificação errado

**Solução:**

```bash
# Verifique o token no .env
cat .env | grep META_VERIFY_TOKEN

# No Meta App, confira se é exatamente o mesmo
# (sem espaços, exato)

# Se ainda não funcionar, gere um novo:
openssl rand -hex 32
# Atualize .env e reinicie
docker-compose restart api
```

---

### ❌ "Webhook registra 200 mas não processa"

**Causa:** Webhook é assincrito, processamento em background falhou

**Solução:**

```bash
# Verifique os logs da API
docker-compose logs -f api | grep "📥"

# Se não vir "📥 Nova mensagem recebida", a mensagem não chegou
# Se vir "📥" mas depois erro, verifique qual:

docker-compose logs api | grep "❌"
```

**Erros comuns:**
- Redis não conectando → `docker-compose restart redis`
- PostgreSQL não conectando → `docker-compose restart postgres`
- Claude API erro → verifique `ANTHROPIC_API_KEY`

---

## 🔴 Problema: Agente não responde

### Sintomas
- Lead manda mensagem
- Webhook recebe
- Agente não retorna resposta
- Lead não recebe nada

### Diagnóstico

**Passo 1:** Verifique se é um erro ou escalação

```bash
docker-compose logs api | grep "5511999999999"
```

Procure por:
- `❌ Erro ao chamar Claude` → problema com IA
- `🚨 Escalando lead` → foi escalado propositalmente
- `🤖 Agente respondeu` → funcionou

**Passo 2:** Teste o agente diretamente

```bash
python scripts/test_agents.py
```

Se der erro aqui, há problema com Claude.

**Passo 3:** Verifique quota de tokens

```bash
# Teste a API de Claude
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-opus","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'
```

---

### ❌ "Erro ao chamar Claude"

**Causa:** API key inválida, expirada ou sem créditos

**Solução:**

```bash
# Verifique a chave
echo $ANTHROPIC_API_KEY

# Vá em https://console.anthropic.com/
# - Confira se a chave é válida
# - Confira se tem créditos (ou ativa trial)
# - Regenere a chave se necessário

# Atualize .env
nano .env
# ANTHROPIC_API_KEY=sk-ant-... (novo valor)

# Reinicie
docker-compose restart api
```

---

### ❌ "Claude retorna erro 429 (rate limit)"

**Causa:** Muitas requisições muito rápido

**Solução:**

```bash
# Aguarde um pouco e tente novamente
# A API tenta retry automaticamente (até 3 vezes)

# Se continuar, pode ter muitos leads simultâneos
# Solução: aumente os workers no docker-compose.yml
```

---

### ❌ "Claude retorna resposta vazia"

**Causa:** Problema raro, pode ser timeout ou parsing

**Solução:**

```bash
# Reinicie a API
docker-compose restart api

# Se continuar, verifique o knowledge base
cat app/knowledge/courses/curso_1.md

# Se knowledge base estiver vazio, o agente não funciona bem
```

---

## 🔴 Problema: Áudios não são enviados

### Sintomas
- Script deveria enviar áudio
- Nada é recebido
- Nenhum log de áudio enviado

### Diagnóstico

**Passo 1:** Verifique se media_id é válido

```bash
# Abra os scripts
cat app/script/schedules/curso_1_script.py | grep "audio"

# Deve ter "audio": "MEDIA_ID_AQUI"
# Se tiver, confirme se o media_id é real
```

**Passo 2:** Teste o upload novamente

```bash
python scripts/upload_audios.py
```

Se der erro, arquivo corrompido ou acesso negado.

**Passo 3:** Verifique os logs

```bash
docker-compose logs api | grep -i audio
```

Procure por:
- `🔊 Áudio enviado por media_id` → sucesso
- `❌ Erro ao executar passo do script` → veja qual é o erro

---

### ❌ "FileNotFoundError: Arquivo de áudio não encontrado"

**Causa:** Arquivo não está em `audios/`

**Solução:**

```bash
# Verifique a estrutura
ls -la audios/

# Deve ter:
# audios/curso_1/01_boas_vindas.mp3
# audios/curso_1/02_diferenciais.mp3
# etc.

# Se não existir, crie os arquivos e rode upload novamente
python scripts/upload_audios.py
```

---

### ❌ "Áudio foi enviado mas lead não recebe"

**Causa:** Meta API ou token inválido

**Solução:**

```bash
# Verifique token
echo $META_ACCESS_TOKEN

# Teste manualmente
curl -X POST "https://graph.facebook.com/v20.0/$META_PHONE_NUMBER_ID/messages" \
  -H "Authorization: Bearer $META_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "5511999999999",
    "type": "audio",
    "audio": {
      "id": "MEDIA_ID_AQUI"
    }
  }'

# Se retorna erro 401, token expirou
# Regenere em https://developers.facebook.com/
```

---

### ❌ "Script lock ativo, pulando"

**Causa:** Áudio anterior ainda sendo enviado, lock previne duplicação

**Solução:**

É normal! Lock dura 120 segundos. Se continuar após esperar:

```bash
# Limpe manualmente o lock
docker-compose exec redis redis-cli DEL "script_lock:5511999999999"

# Tente novamente
```

---

## 🔴 Problema: Lead não chega no agente (Webhook do SprintHub/CRM)

### Sintomas
- Lead se cadastra no site e aparece no SprintHub
- O agente não envia a primeira mensagem/template
- No monitor do agente, o lead não entra em “Nurturing”

### Checklist rápido

**1) URL do webhook**

O endpoint correto do agente é:

```
POST https://SEU_DOMINIO/webhook/sprinthub
```

**2) Autorização (401 Unauthorized)**

O webhook do CRM exige `APP_SECRET`. Envie **um** dos headers:
- `X-Webhook-Key: <APP_SECRET>` (recomendado)
- `Authorization: Bearer <APP_SECRET>` (fallback)

**3) Corpo inválido (400 Invalid JSON / Empty body)**

O agente espera JSON. Se houver middleware (ex.: Zapier/Make/n8n), confirme que ele está enviando JSON no body.

**4) Lead ignorado (status=ignored)**

Se o retorno do webhook vier como `ignored`, confira o motivo:
- `missing_phone`: não encontrou telefone/WhatsApp no payload
- `activation_not_matched`: não conseguiu mapear o curso/produto do lead

**5) Logs do container**

```bash
docker-compose logs api | grep -i \"Webhook SprintHub\"
docker-compose logs api | grep -i \"SprintHub ignorado\"
```

### Teste manual (recomendado)

```bash
APP_SECRET=seu-segredo-forte ./test_crm_webhook.sh http://localhost:8000 5511999999999 pos_fisio_neuro
```

---

## 🔴 Problema: Lead não aparece no SprintHub

### Sintomas
- Lead foi criado na API
- SprintHub não tem o card
- CRM não está sincronizado

### Diagnóstico

**Passo 1:** Verifique credenciais

```bash
cat .env | grep SPRINTHUB
```

Confirme que `SPRINTHUB_API_KEY` não está vazio.

**Passo 2:** Verifique pipelines

```bash
cat .env | grep PIPELINE
```

Deve ter:
```
SPRINTHUB_PIPELINE_CURSO_1=12345
SPRINTHUB_PIPELINE_CURSO_2=67890
SPRINTHUB_PIPELINE_POS_FISIO_NEURO=24680
```

**Passo 3:** Verifique logs

```bash
docker-compose logs api | grep -i sprinthub
```

---

### ❌ "Erro ao criar lead no SprintHub"

**Causa:** Pipeline ID inválido ou API key errada

**Solução:**

```bash
# Acesse SprintHub
# Vá em um pipeline
# URL deve ser: https://app.sprinthub.com/... /pipelines/12345/

# Copie o ID (12345) e atualize .env
nano .env
# SPRINTHUB_PIPELINE_CURSO_1=12345

# Reinicie
docker-compose restart api

# Teste novamente
bash test_webhook.sh http://localhost:8000 5511999999999
```

---

## 🔴 Problema: Banco de dados cheio ou lento

### Sintomas
- Queries lentas
- Disco cheio
- PostgreSQL travado

### Diagnóstico

**Passo 1:** Limpe conversas antigas

```bash
docker-compose exec postgres psql -U sales_agent -d sales_agent_db \
  -c "SELECT COUNT(*) FROM conversations;"

# Se > 1 milhão, pode estar lento
```

**Passo 2:** Delete antigas

```bash
docker-compose exec postgres psql -U sales_agent -d sales_agent_db \
  -c "DELETE FROM conversations WHERE created_at < NOW() - INTERVAL '30 days';"
```

**Passo 3:** Analyze

```bash
docker-compose exec postgres psql -U sales_agent -d sales_agent_db \
  -c "ANALYZE;"
```

---

### ❌ "FATAL: remaining connection slots reserved for non-replication superuser connections"

**Causa:** Muitas conexões abertas

**Solução:**

```bash
# Reinicie PostgreSQL
docker-compose restart postgres

# Se continuar, aumente pool_size em app/db/database.py
```

---

## 🟡 Problema: Lentidão em Produção

### Sintomas
- Respostas lentas (> 5 segundos)
- CPU alta
- Memória alta

### Diagnóstico

**Passo 1:** Monitore recursos

```bash
docker stats
```

Verifique:
- CPU: se > 50%, aumentar workers
- MEM: se > 60%, aumentar limite ou limpar dados

**Passo 2:** Aumentar workers

```yaml
# docker-compose.yml
api:
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Reinicie: `docker-compose restart api`

**Passo 3:** Otimize queries

```bash
# Adicione índices ao PostgreSQL
docker-compose exec postgres psql -U sales_agent -d sales_agent_db \
  -c "CREATE INDEX idx_phone ON leads(phone_number);"
```

---

## 🟡 Problema: SSL/HTTPS não funciona

### Sintomas
- `curl https://seu-dominio.com/health` retorna erro
- Certificado inválido
- HTTPS não ativa

### Diagnóstico

**Passo 1:** Verifique certificado

```bash
certbot certificates
```

Deve listar seu domínio.

**Passo 2:** Teste acesso

```bash
curl -v https://seu-dominio.com/health
```

Se retorna `SSL: CERTIFICATE_VERIFY_FAILED`, certificado expirou.

**Passo 3:** Renove

```bash
certbot renew --force-renewal
systemctl restart nginx
```

---

### ❌ "Certificado expirado"

**Solução:**

```bash
# Renew manual
certbot renew --force-renewal

# Verifique
certbot certificates

# Reinicie nginx
systemctl restart nginx
```

---

### ❌ "Nginx não inicia"

**Solução:**

```bash
# Teste configuração
nginx -t

# Se há erro, veja qual:
cat /etc/nginx/sites-enabled/sales-agent

# Corrija e tente novamente
systemctl restart nginx
```

---

## 📞 Se Nada Disso Funcionar

1. **Coleta logs completos:**
   ```bash
   docker-compose logs > logs.txt
   ```

2. **Tira screenshot dos erros**

3. **Reproduz passo a passo:**
   - O que você fez
   - Qual era o resultado esperado
   - Qual foi o resultado real

4. **Abre issue no GitHub** com essas informações

---

## ✅ Checklist de Debug

Antes de reportar um bug:

- [ ] Verifiquei `.env` (não está vazio?)
- [ ] Rodei `docker-compose logs` para ver erro específico
- [ ] Tentei reiniciar os containers: `docker-compose restart`
- [ ] Tentei limpar e rebuildar: `docker-compose down && docker-compose up -d --build`
- [ ] Procurei em FAQ.md
- [ ] Procurei em TROUBLESHOOTING.md (este arquivo)
- [ ] Verifiquei que eu sigo os pré-requisitos (Python, Docker, etc.)

---

**Se ainda assim não funcionar, não desista! Procure na comunidade ou abra uma issue. 🚀**
