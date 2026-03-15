# ✅ Checklist de Pré-Produção

Antes de colocar seu Sales Agent ao vivo, garanta que tudo está pronto!

---

## 🎯 Fase 1: Configuração da IA

- [ ] Agente Curso 1 tem nome, profissão e personalidade definidos
- [ ] Agente Curso 2 tem nome, profissão e personalidade definidos
- [ ] System prompt de ambos os agentes tem exemplos de respostas boas/ruins
- [ ] Knowledge base do Curso 1 está 100% completa (preços, grade, depoimentos)
- [ ] Knowledge base do Curso 2 está 100% completa
- [ ] Testou os agentes localmente com `python scripts/test_agents.py`
- [ ] Agentes parecem humanos (não robóticos)
- [ ] Agentes respondem em português brasileiro natural
- [ ] Agentes não revelam ser IA em nenhuma situação
- [ ] Respostas são curtas (máx 3-4 linhas)
- [ ] Emojis são usados com moderação e naturalidade

---

## 🎙️ Fase 2: Áudios e Script

- [ ] Áudios gravados para Curso 1 (5 passos mínimo)
- [ ] Áudios gravados para Curso 2 (5 passos mínimo)
- [ ] Áudios em formato MP3 ou OGG, 128 kbps
- [ ] Áudios testados (qualidade, clareza, duração)
- [ ] Áudios organizados em `audios/curso_1/` e `audios/curso_2/`
- [ ] Upload realizado: `python scripts/upload_audios.py`
- [ ] Media IDs salvos em `audio_media_ids.json`
- [ ] Scripts atualizados com media IDs corretos
- [ ] Delays configurados conforme estratégia de funil
- [ ] Triggers (auto vs response) bem definidos
- [ ] Pre-text e post-text personalizados
- [ ] Testou o script end-to-end com um lead fictício

---

## 🤝 Fase 3: Integrações Externas

### Meta WhatsApp API
- [ ] Aplicação criada em https://developers.facebook.com/
- [ ] Número WhatsApp Business adicionado
- [ ] Phone Number ID obtido
- [ ] Access Token permanente gerado
- [ ] Webhook URL será configurada pós-deploy

### Anthropic Claude
- [ ] Conta criada em https://console.anthropic.com/
- [ ] API Key gerada
- [ ] Quota de tokens verificada (tem créditos?)
- [ ] Modelo `claude-sonnet-4-5` ativado

### SprintHub (CRM)
- [ ] Conta ativa no SprintHub
- [ ] Pipeline para Curso 1 criado
- [ ] Pipeline para Curso 2 criado
- [ ] IDs dos pipelines em mãos
- [ ] API Key gerada e testada
- [ ] Campos customizados criados (curso, origem, etc.)

---

## 💻 Fase 4: Infraestrutura Local

- [ ] Docker instalado (`docker --version`)
- [ ] Docker Compose instalado (`docker-compose --version`)
- [ ] Repositório clonado localmente
- [ ] `.env` criado com todas as variáveis
- [ ] `docker-compose up -d` funciona sem erros
- [ ] Todos os containers rodando: `docker-compose ps`
- [ ] API responde: `curl http://localhost:8000/health`
- [ ] PostgreSQL inicializado com tabelas
- [ ] Redis conectado: `docker-compose exec redis redis-cli PING`

---

## 🧪 Fase 5: Testes Funcionais Locais

- [ ] Webhook verifica corretamente via GET
- [ ] Webhook recebe mensagens via POST
- [ ] Lead criado no Redis ao receber primeira mensagem
- [ ] Histórico salvos nas conversas
- [ ] Agente responde com Claude
- [ ] Agente responde em tempo razoável (< 5 seg)
- [ ] Agente não está responsável por erros de API
- [ ] Script de áudios executa sem erros
- [ ] Áudios são disparados conforme schedule
- [ ] Lead é sincronizado com CRM (SprintHub)
- [ ] Escalação funciona (leva para "escalated")
- [ ] Alertas de escalação vão para o número certo

Teste com:
```bash
./test_webhook.sh http://localhost:8000 5511999999999
```

---

## 📱 Fase 6: Testes com WhatsApp Real (Opcional)

Se quiser testar ANTES de ir para produção:

- [ ] Use ngrok: `ngrok http 8000`
- [ ] Configure webhook temporário no Meta
- [ ] Envie mensagens de teste via WhatsApp
- [ ] Verifique que leva o tempo esperado para responder
- [ ] Verifique que áudios são enviados
- [ ] Verifique que agente responde além dos áudios
- [ ] Simule uma conversa completa (boas-vindas → CTA)
- [ ] Teste escalação (fale com humano)

---

## 🚀 Fase 7: VPS e Deploy

### Hostinger VPS
- [ ] VPS provisionada (Ubuntu 22.04+)
- [ ] SSH acesso testado
- [ ] Domínio criado e apontando para IP da VPS
- [ ] Sistema atualizado: `apt update && apt upgrade -y`

### Docker em Produção
- [ ] Docker instalado na VPS
- [ ] Docker Compose instalado
- [ ] Repositório clonado em `/opt/sales-agent`
- [ ] `.env` preenchido com valores reais
- [ ] `docker-compose up -d` executado
- [ ] Containers rodando sem erros

### SSL/HTTPS
- [ ] Nginx instalado
- [ ] Configuração do nginx criada
- [ ] Certbot instalado
- [ ] SSL certificado gerado: `certbot --nginx -d seu-dominio.com`
- [ ] HTTPS funcionando: `curl https://seu-dominio.com/health`
- [ ] Redirecionamento HTTP → HTTPS ativo

### Firewall
- [ ] UFW habilitado: `ufw enable`
- [ ] Portas abertas: 22 (SSH), 80 (HTTP), 443 (HTTPS)
- [ ] Outras portas fechadas

---

## 🔗 Fase 8: Webhook Meta

- [ ] Acesse https://developers.facebook.com/ → Sua App → WhatsApp
- [ ] Em "Configuração", vá para "Webhooks"
- [ ] Clique em "Gerenciar Webhooks" (ou "Edit")
- [ ] URL do Webhook: `https://seu-dominio.com/webhook/whatsapp`
- [ ] Token de Verificação: `seu-META_VERIFY_TOKEN`
- [ ] Subscribe em: `messages` e `message_status`
- [ ] Clique em "Verificar e Salvar"
- [ ] Verifique que recebeu "✓ Verificado" (status verde)
- [ ] Teste enviando uma mensagem real via WhatsApp

---

## 📊 Fase 9: Monitoramento e Logging

- [ ] Logs da API salvos (`docker-compose logs` funciona)
- [ ] Nginx logs monitorados (`/var/log/nginx/`)
- [ ] PostgreSQL logs verificados
- [ ] Redis logs verificados
- [ ] Script de health check criado
- [ ] Crontab configurado para rodar health check a cada 5 min
- [ ] Backup do banco agendado (diário ou semanal)

---

## 🎓 Fase 10: Conhecimento Técnico

Você está preparado para:
- [ ] Acessar VPS via SSH
- [ ] Ver logs: `docker-compose logs -f api`
- [ ] Reiniciar containers: `docker-compose restart api`
- [ ] Atualizar código: `git pull && docker-compose up -d --build`
- [ ] Fazer backup: `docker exec sales_agent_postgres pg_dump ...`
- [ ] Acessar PostgreSQL: `docker-compose exec postgres psql ...`
- [ ] Testar webhook: `curl -X POST ...`
- [ ] Gerar relatório: `python scripts/generate_report.py`

---

## ⚠️ Pré-Produção: Últimas Verificações

### Segurança
- [ ] `.env` nunca foi commitado no Git
- [ ] Senhas são fortes (>16 caracteres, mix de tudo)
- [ ] `META_ACCESS_TOKEN` é um token PERMANENTE (não de curta duração)
- [ ] `ANTHROPIC_API_KEY` está segura (nunca compartilhe)
- [ ] `SPRINTHUB_API_KEY` está segura
- [ ] Permissões de arquivo: `.env` tem `600`
- [ ] Firewall está configurado adequadamente
- [ ] Fail2ban ou proteção similar está ativa

### Performance
- [ ] API responde em < 2 segundos (testes de carga básicos)
- [ ] Redis não está usando 100% de RAM
- [ ] PostgreSQL não está travado
- [ ] Nginx está balanceando corretamente
- [ ] Timeouts configurados no Nginx (60s+ para webhooks)

### Conformidade
- [ ] Política de privacidade pronta (GDPR/LGPD)
- [ ] Termos de uso prontos
- [ ] Consentimento para WhatsApp documentado
- [ ] Retenção de dados documentada (quanto tempo mantém conversas?)

---

## 🟢 Status Final

Quando tudo acima estiver ✅:

```bash
echo "🚀 Sales Agent está pronto para produção!"
```

**Você está autorizado a:**
1. ✅ Registrar webhook no Meta
2. ✅ Agendar leads reais para o sistema
3. ✅ Monitorar conversões no SprintHub
4. ✅ Iterar e melhorar os agentes

---

## 📈 Pós-Launch (Primeiras 2 Semanas)

- [ ] Monitore 10+ conversas reais
- [ ] Identifique objeções mais comuns
- [ ] Ajuste prompts dos agentes
- [ ] Melhore knowledge bases
- [ ] Acompanhe taxa de conversão
- [ ] Verifique se escalações funcionam
- [ ] Teste com leads de diferentes perfis
- [ ] Documente aprendizados

---

## 🎉 Parabéns!

Seu Sales Agent está **PRONTO PARA PRODUÇÃO**! 

Próximas ações:
1. Envie o link para seus leads
2. Acompanhe as conversas nos logs
3. Monitore SprintHub para conversões
4. Itere com base em feedback
5. Escale quando estiver confiante

**Boa sorte! 🚀**
