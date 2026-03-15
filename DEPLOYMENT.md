# 🚀 Guia de Deploy na Hostinger VPS

Passo a passo para colocar sua Sales Agent em produção na Hostinger.

---

## 📋 Pré-requisitos

- [ ] VPS Hostinger com **Ubuntu 22.04** (ou similar)
- [ ] Acesso SSH (deve ter recebido as credenciais por e-mail)
- [ ] Domínio configurado e apontando para o IP da VPS
- [ ] Todas as variáveis de ambiente prontas (`.env`)

---

## 1️⃣ Acesse a VPS via SSH

```bash
ssh root@seu-vps-ip
# Digite a senha quando pedido
```

Ou se tiver chave SSH:

```bash
ssh -i /path/to/key.pem root@seu-vps-ip
```

---

## 2️⃣ Atualize o Sistema

```bash
apt update && apt upgrade -y
```

---

## 3️⃣ Instale Docker e Docker Compose

### Install Docker:

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker root
```

### Install Docker Compose:

```bash
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
docker-compose --version
```

---

## 4️⃣ Crie a estrutura de diretórios

```bash
mkdir -p /opt/sales-agent
cd /opt/sales-agent
```

---

## 5️⃣ Clone o repositório

```bash
# Opção A: Se seu repo é público
git clone https://github.com/seu-usuario/sales-agent.git .

# Opção B: Se é privado, use personal access token
git clone https://seu-username:seu-token@github.com/seu-usuario/sales-agent.git .
```

---

## 6️⃣ Configure o arquivo `.env`

```bash
nano .env
```

Cole as seguintes variáveis (substitua pelos seus valores reais):

```env
# ── Aplicação ──────────────────────────────────────────────
APP_ENV=production
APP_SECRET=gere-uma-string-aleatoria-forte
LOG_LEVEL=INFO

# ── WhatsApp (Meta API Oficial) ────────────────────────────
META_VERIFY_TOKEN=seu-token-de-verificacao
META_ACCESS_TOKEN=seu-token-permanente-aqui
META_PHONE_NUMBER_ID=seu-phone-number-id
META_API_VERSION=v20.0

# ── Claude (Anthropic) ─────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5

# ── Redis ──────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0
SESSION_TTL_HOURS=48

# ── PostgreSQL ─────────────────────────────────────────────
POSTGRES_USER=sales_agent
POSTGRES_PASSWORD=gere-uma-senha-forte-aqui
POSTGRES_DB=sales_agent_db
DATABASE_URL=postgresql+asyncpg://sales_agent:sua-senha@postgres:5432/sales_agent_db

# ── SprintHub (CRM) ────────────────────────────────────────
SPRINTHUB_API_URL=https://api.sprinthub.com.br
SPRINTHUB_API_KEY=sua-chave-api-sprinthub
SPRINTHUB_PIPELINE_CURSO_1=seu-pipeline-id-1
SPRINTHUB_PIPELINE_CURSO_2=seu-pipeline-id-2

# ── Escalação para Humano ──────────────────────────────────
ESCALATION_WHATSAPP_NUMBER=5511999999999

# ── Cursos ─────────────────────────────────────────────────
COURSE_SLUGS=curso_1,curso_2
```

**Pressione Ctrl+X → Y → Enter para salvar**

---

## 7️⃣ Inicie os containers

```bash
docker-compose up -d
```

Verifique se tudo subiu:

```bash
docker-compose ps
```

Você deve ver algo como:

```
NAME                  COMMAND                 STATUS
sales_agent_api       "uvicorn app.main..."   Up
sales_agent_redis     "redis-server"          Up
sales_agent_postgres  "postgres"              Up
```

---

## 8️⃣ Verifique a saúde da API

```bash
curl http://localhost:8000/health
```

Deve retornar:

```json
{"status": "ok", "env": "production"}
```

---

## 9️⃣ Configure Nginx (Reverse Proxy + SSL)

### Instale Nginx:

```bash
apt install -y nginx certbot python3-certbot-nginx
```

### Crie arquivo de configuração:

```bash
nano /etc/nginx/sites-available/sales-agent
```

Cole:

```nginx
server {
    listen 80;
    server_name seu-dominio.com;

    # Redireciona HTTP para HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name seu-dominio.com;

    # SSL será configurado pelo Certbot abaixo
    ssl_certificate /etc/letsencrypt/live/seu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/seu-dominio.com/privkey.pem;

    # Configurações SSL recomendadas
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Proxy reverso para a FastAPI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;

        # Timeouts para webhook
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Logs
    access_log /var/log/nginx/sales-agent-access.log;
    error_log /var/log/nginx/sales-agent-error.log;
}
```

### Habilite o site:

```bash
ln -s /etc/nginx/sites-available/sales-agent /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default  # Remove default
nginx -t  # Testa configuração
systemctl restart nginx
```

### Configure SSL com Certbot:

```bash
certbot --nginx -d seu-dominio.com
# Siga as instruções e escolha "2" para redirecionar HTTP para HTTPS
```

Verifique o SSL:

```bash
curl https://seu-dominio.com/health
```

---

## 🔟 Configure o Webhook no Meta App

1. Acesse [Meta App Manager](https://developers.facebook.com/)
2. Vá até sua App → Configurações → Produto WhatsApp → Configuração
3. Em "Webhook URL", coloque:
   ```
   https://seu-dominio.com/webhook/whatsapp
   ```

4. Em "Token de Verificação", coloque o valor do `META_VERIFY_TOKEN` do seu `.env`

5. Clique em "Verificar e Salvar"

6. Meta vai fazer um GET na sua URL para testar — deve receber 200 OK

---

## 1️⃣1️⃣ Monitore os Logs

### Logs da API:

```bash
docker-compose logs -f api
```

### Logs do Nginx:

```bash
tail -f /var/log/nginx/sales-agent-access.log
```

### Logs do sistema:

```bash
journalctl -u docker -f
```

---

## 1️⃣2️⃣ Backup e Persistência de Dados

### Backup do PostgreSQL:

```bash
docker exec sales_agent_postgres pg_dump -U sales_agent sales_agent_db > backup_$(date +%Y%m%d).sql
```

### Restore do backup:

```bash
cat seu-backup.sql | docker exec -i sales_agent_postgres psql -U sales_agent sales_agent_db
```

---

## 1️⃣3️⃣ Auto-restart em caso de falha

Verifique que os containers têm a política `restart: unless-stopped` no `docker-compose.yml`:

```yaml
services:
  api:
    # ...
    restart: unless-stopped
```

Se algo cair, Docker vai reiniciar automaticamente.

---

## 1️⃣4️⃣ Atualizações e Redeploy

Para atualizar o código:

```bash
cd /opt/sales-agent
git pull origin main
docker-compose up -d --build  # Reconstrói as imagens
```

Para verificar se atualizou:

```bash
docker-compose logs -f api | head -20
```

---

## 1️⃣5️⃣ Escalonamento (Opcional)

Se a carga ficar muito alta, você pode:

### Aumentar workers da API:

No `docker-compose.yml`:

```yaml
api:
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Escalar containers:

```bash
docker-compose up -d --scale api=3  # 3 instâncias de API
```

(Vai precisar de um load balancer — Nginx já faz isso por padrão)

---

## 🔐 Segurança

### Firewall (UFW):

```bash
ufw enable
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw status
```

### Fail2ban (proteção contra brute force):

```bash
apt install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban
```

### Senhas e Secrets:

- ✅ Nunca commite `.env` no Git
- ✅ Use `.env` com permissão `600`:
  ```bash
  chmod 600 .env
  ```
- ✅ Gere senhas fortes:
  ```bash
  openssl rand -base64 32
  ```

---

## 🆘 Troubleshooting

### "Conexão recusada quando acessa https://seu-dominio.com"

1. Verifique Nginx está rodando:
   ```bash
   systemctl status nginx
   ```
2. Verifique API está rodando:
   ```bash
   docker-compose ps
   ```
3. Verifique firewall:
   ```bash
   ufw status
   ```

### "Webhook não está recebendo mensagens"

1. Teste a URL manualmente:
   ```bash
   curl -X GET "https://seu-dominio.com/webhook/whatsapp?hub.verify_token=seu-token&hub.challenge=123"
   ```
2. Verifique logs:
   ```bash
   docker-compose logs -f api | grep webhook
   ```

### "PostgreSQL está cheio"

1. Limpe conversas antigas:
   ```bash
   docker exec sales_agent_postgres psql -U sales_agent -d sales_agent_db \
     -c "DELETE FROM conversations WHERE created_at < NOW() - INTERVAL '30 days';"
   ```

### "Redis está lento"

1. Reinicie:
   ```bash
   docker-compose restart redis
   ```
2. Monitore memória:
   ```bash
   docker stats redis
   ```

---

## 📊 Health Check Script

Crie um script para monitorar a saúde:

```bash
nano /opt/sales-agent/healthcheck.sh
```

Cole:

```bash
#!/bin/bash

# Verifica API
API_HEALTH=$(curl -s http://localhost:8000/health || echo "failed")
if [ "$API_HEALTH" != '{"status":"ok","env":"production"}' ]; then
    echo "❌ API DOWN!"
    docker-compose restart api
fi

# Verifica PostgreSQL
POSTGRES_HEALTH=$(docker-compose exec -T postgres pg_isready -U sales_agent || echo "failed")
if [[ "$POSTGRES_HEALTH" != *"accepting"* ]]; then
    echo "❌ PostgreSQL DOWN!"
    docker-compose restart postgres
fi

# Verifica Redis
REDIS_HEALTH=$(docker-compose exec -T redis redis-cli ping || echo "failed")
if [ "$REDIS_HEALTH" != "PONG" ]; then
    echo "❌ Redis DOWN!"
    docker-compose restart redis
fi

echo "✅ Tudo OK - $(date)"
```

Adicione ao crontab para rodar a cada 5 minutos:

```bash
chmod +x /opt/sales-agent/healthcheck.sh
crontab -e
```

Cole:

```
*/5 * * * * /opt/sales-agent/healthcheck.sh >> /opt/sales-agent/healthcheck.log 2>&1
```

---

## ✅ Checklist de Deploy

- [ ] VPS criada e acesso SSH confirmado
- [ ] Docker e Docker Compose instalados
- [ ] Repositório clonado em `/opt/sales-agent`
- [ ] Arquivo `.env` preenchido com valores reais
- [ ] Containers iniciados e rodando
- [ ] API respondendo no `localhost:8000`
- [ ] Nginx configurado com SSL
- [ ] Domínio apontando para a VPS
- [ ] Certbot SSL ativo
- [ ] Webhook registrado no Meta App
- [ ] Teste com mensagem de WhatsApp bem-sucedido
- [ ] Logs sendo monitorados
- [ ] Firewall configurado
- [ ] Backup agendado

---

## 🎉 Pronto!

Sua Sales Agent está ao vivo! 

Próximas ações:
1. Monitore os logs: `docker-compose logs -f api`
2. Teste com leads reais
3. Ajuste os prompts dos agentes conforme necessário
4. Estude as objeções que surgem e melhore as respostas
5. Monitore a taxa de conversão no SprintHub

---

**Boa sorte com seu agente de vendas! 🚀**

Para dúvidas de produção: verifique sempre `docker-compose logs -f api`
