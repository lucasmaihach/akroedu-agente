# 📜 Changelog — Histórico de Versões

Todas as mudanças, melhorias e correções do Sales Agent.

---

## [1.0.0] — 2024-01-15

### 🎉 Initial Release

**Recursos principais:**
- ✅ Webhook WhatsApp (Meta API oficial)
- ✅ IA conversacional (Claude Sonnet)
- ✅ Múltiplos agentes por curso
- ✅ Script de áudios automático
- ✅ Roteador inteligente
- ✅ Escalação para humano
- ✅ Integração SprintHub
- ✅ Cache Redis
- ✅ Persistência PostgreSQL
- ✅ Docker Compose
- ✅ Documentação completa

**Agentes inclusos:**
- Ana (Curso 1 — MBA)
- Carlos (Curso 2 — Pós Tech)

**Banco de dados:**
- Tabela `leads`
- Tabela `conversations`
- Tabela `audio_logs`

**Comandos úteis:**
- `make setup` — Setup inicial
- `make test-agents` — Testa agentes
- `make upload-audios` — Upload de áudios
- `make backup-db` — Backup do banco

---

## [1.1.0] — Próxima Versão (Planejado)

### 🚀 Melhorias Esperadas

**Agentes:**
- [ ] Suporte a mais de 2 cursos dinamicamente
- [ ] Sistema de feedback do lead para agente aprender
- [ ] A/B testing de prompts

**Áudios:**
- [ ] Suporte a vídeos em vez de áudios
- [ ] Geração automática de áudios via TTS
- [ ] Analytics de engajamento por áudio

**CRM:**
- [ ] Integração com mais CRMs (HubSpot, RD Station, etc.)
- [ ] Webhook bidirecional
- [ ] Sincronização de histórico completo

**IA:**
- [ ] Troca dinâmica de modelos (Groq, OpenAI, etc.)
- [ ] Fine-tuning automático com dados históricos
- [ ] Análise de sentimento do lead

**Infraestrutura:**
- [ ] Kubernetes deployment
- [ ] Load balancer automático
- [ ] Autoscaling
- [ ] Monitoring com Prometheus/Grafana

**Documentação:**
- [ ] Vídeos tutorial
- [ ] Guia de best practices
- [ ] Case studies de sucesso

---

## 🔄 Como Reportar Bugs

Se encontrar um bug:

1. **Descreva o problema**
   - Qual era o comportamento esperado?
   - Qual foi o comportamento real?
   - Como reproduzir?

2. **Coleta informações**
   ```bash
   # Versão do código
   git log -1 --oneline
   
   # Versão do Docker
   docker --version
   
   # Logs
   docker-compose logs > logs.txt
   ```

3. **Abre uma issue** com essas informações

---

## 🎯 Roadmap (2024-2025)

### Q1 2024
- [x] Lançamento v1.0.0
- [ ] Feedback inicial de usuários
- [ ] Correção de bugs críticos

### Q2 2024
- [ ] Suporte a mais cursos dinamicamente
- [ ] Integração com mais CRMs
- [ ] Melhorias de performance

### Q3 2024
- [ ] TTS automático para áudios
- [ ] Análise de sentimento
- [ ] Dashboard de métricas

### Q4 2024
- [ ] Kubernetes deployment
- [ ] Multi-language support
- [ ] Advanced analytics

---

## 📝 Versionamento

Seguimos **Semantic Versioning** (MAJOR.MINOR.PATCH):

- **MAJOR** (1.0.0 → 2.0.0): Mudanças breaking
- **MINOR** (1.0.0 → 1.1.0): Novos recursos
- **PATCH** (1.0.0 → 1.0.1): Bug fixes

---

## 🔄 Atualizando para Novas Versões

### Do v1.0.0 para v1.1.0

```bash
# 1. Faça backup
make backup-db

# 2. Atualize código
git pull origin main

# 3. Rebuild
docker-compose down
docker-compose up -d --build

# 4. Teste
curl http://localhost:8000/health
```

---

## ✨ Contribuindo

Quer contribuir? Ótimo! 

### Passos:

1. Fork o repositório
2. Crie uma branch: `git checkout -b feature/sua-feature`
3. Commit: `git commit -m "Adiciona sua-feature"`
4. Push: `git push origin feature/sua-feature`
5. Abra um Pull Request

### Diretrizes:

- ✅ Mantenha compatibilidade com versão anterior
- ✅ Adicione testes se possível
- ✅ Atualize documentação
- ✅ Siga o padrão de código existente
- ✅ Descreva bem seu PR

---

## 📚 Recursos para Desenvolvedores

- **GitHub:** [seu-repo-aqui]
- **Issues:** Reportar bugs e sugestões
- **Discussions:** Discussões e ideias
- **Wiki:** Documentação avançada

---

## 🙏 Créditos

- **Claude Sonnet** — IA conversacional
- **Meta WhatsApp API** — Integração
- **FastAPI** — Framework web
- **SprintHub** — CRM integrado

---

## 📄 Licença

Este projeto está sob licença MIT.
Você é livre para usar, modificar e distribuir.

Veja `LICENSE` para detalhes completos.

---

## 📞 Suporte

- **Documentação:** Veja `README.md` e `INDEX.md`
- **Perguntas:** Veja `FAQ.md`
- **Problemas:** Veja `TROUBLESHOOTING.md`
- **Issues:** Abra no GitHub

---

**Obrigado por usar Sales Agent! 🚀**

Se gostou, considere dar uma ⭐ no GitHub!
