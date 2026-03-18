# Contexto do Projeto (para iniciar um novo chat)

Este arquivo serve como **resumo rápido e atualizado** do projeto para você colar em um novo chat e acelerar o entendimento do assistente.

---

## 1) Objetivo do projeto

Sistema de atendimento e vendas via **WhatsApp (Meta Cloud API)** com:
- qualificação de leads,
- execução de script comercial (texto, áudio e imagens),
- respostas controladas por regras em momentos críticos,
- integração com CRM (SprintHub),
- possibilidade de escalonamento para humano.

---

## 2) Stack técnica

- **Python 3.11**
- **FastAPI + Uvicorn**
- **Redis (redis.asyncio)** para sessão, estado do lead, histórico, locks e cache
- **PostgreSQL + asyncpg**
- **Anthropic (Claude)**
- **Meta WhatsApp Cloud API** via `httpx`
- **tenacity** (retry)
- **pytest + pytest-asyncio**
- **Docker Compose**
- **structlog**, **pydantic/pydantic-settings**

---

## 3) Arquitetura (alto nível)

- `app/agents/router_agent.py`: roteamento/classificação inicial.
- `app/agents/dispatcher.py`: orquestra lógica principal por fase da conversa.
- `app/script/engine.py`: executa script (passos, delays, mídia).
- `app/script/schedules/*`: scripts por curso.
- `app/services/whatsapp.py`: envio de mensagens/mídias para Meta.
- `app/services/escalation.py`: alertas para atendimento humano.
- `app/services/crm.py`: integração de estágios/pipeline no SprintHub.
- `app/models/lead.py`: modelo de lead e estados.

---

## 4) Cursos e configuração atual

Hoje o sistema considera 3 slugs de curso:
- `curso_1`
- `curso_2`
- `pos_fisio_neuro`

Variáveis importantes:
- `COURSE_SLUGS=curso_1,curso_2,pos_fisio_neuro`
- `SPRINTHUB_PIPELINE_CURSO_1=...`
- `SPRINTHUB_PIPELINE_CURSO_2=...`
- `SPRINTHUB_PIPELINE_POS_FISIO_NEURO=...`

> Conferir `env.example`, `README.md`, `FIRST_RUN.md`, `DEPLOYMENT.md`.

---

## 5) Funcionalidade recente (mais importante)

### FAQ controlada para `pos_fisio_neuro` durante script ativo (antes de preço)

Arquivo novo:
- `app/agents/courses/pos_fisio_neuro_faq.py`

Comportamento em `app/agents/dispatcher.py` quando `script_active=True` e curso `pos_fisio_neuro`:
1. Se o lead perguntar **preço**:
   - 1ª vez: redireciona e pausa fluxo conforme regra existente.
   - 2ª vez: pula para `price_skip_to_step`.
2. Se não for preço, tenta casar FAQ (`match_faq_response`).
3. Se FAQ casada:
   - responde texto fixo da intenção.
   - se intenção sensível (`notify_human=True`), notifica humano via WhatsApp.
4. Se FAQ **não casada**:
   - responde fallback educado,
   - notifica humano via WhatsApp,
   - **retorna `False`** (não auto-avança script nesse ponto).

### Escalonamento sem trocar estágio

Novo método em `app/services/escalation.py`:
- `notify_human_only(lead, reason, user_message="")`

Esse método:
- envia alerta ao número humano (`ESCALATION_WHATSAPP_NUMBER`),
- **não** marca lead como escalado,
- **não** muda estágio no fluxo.

---

## 6) Estado atual conhecido

- Testes: **passando** (`pytest`: 4/4).
- Webhook da Meta: funcionando com ngrok.
- Fluxo real em WhatsApp: validado.
- Áudios no script de `pos_fisio_neuro`: funcionando via **media_id**.
- Imagens do script: reabilitadas após ajustes de sintaxe.

---

## 7) Problemas recentes já resolvidos

1. **Teardown do Redis no pytest-asyncio**
   - corrigido em `tests/conftest.py` (ordem de limpeza/close).

2. **Drift de documentação e env para novo curso**
   - docs e `env.example` atualizados para 3 cursos.

3. **`scripts/create_course.py` desatualizado**
   - ajustado para arquitetura atual (script config, assinatura `script_active`, passos manuais).

4. **Parada antes do envio de áudio**
   - causa: upload de arquivo local no ambiente.
   - solução: usar `media_id` nos passos do script.

5. **Imagens não enviando**
   - foram desativadas temporariamente e depois reativadas.
   - corrigidos erros de sintaxe (vírgulas faltando).

---

## 8) Pendências / próximos testes recomendados

1. Validar em chat real os cenários FAQ (pré-preço):
   - FAQ mapeada (ex.: aula ao vivo, professores),
   - FAQ sensível (ex.: cancelamento/reembolso),
   - pergunta fora do mapeamento.

2. Confirmar recebimento do alerta humano no WhatsApp para:
   - FAQs sensíveis,
   - perguntas não mapeadas.

3. Decidir política final para pergunta não mapeada durante script ativo:
   - manter `return False` (pausa),
   - ou mudar para `True` (continua script).

4. Segurança:
   - se token Meta foi exposto em algum contexto, **rotacionar/revogar** fora do código.

---

## 9) Comandos úteis (local)

Subir ambiente:
```bash
make up
```

Rodar testes:
```bash
pytest -q
```

Rodar script de teste de agentes:
```bash
python -m scripts.test_agents
```

Healthcheck API:
```bash
curl -s http://localhost:8000/health
```

---

## 10) Prompt sugerido para colar em novo chat

"Estou trabalhando em um agente de vendas via WhatsApp com FastAPI/Redis/Postgres. O projeto já tem scripts por curso, integração Meta Cloud API e controle de fluxo no dispatcher. Quero continuar a partir do arquivo `CONTEXTO_NOVO_CHAT.md` (raiz do projeto). Leia esse arquivo e me ajude com [OBJETIVO_ATUAL]."

---

## 11) Arquivos-chave para referência rápida

- `CONTEXTO_NOVO_CHAT.md` (este arquivo)
- `README.md`
- `FIRST_RUN.md`
- `DEPLOYMENT.md`
- `env.example`
- `app/agents/dispatcher.py`
- `app/agents/courses/pos_fisio_neuro_faq.py`
- `app/services/escalation.py`
- `app/script/schedules/pos_fisio_neuro_script.py`
- `tests/conftest.py`

---

Se este arquivo ficar desatualizado, atualize primeiro aqui para manter o handoff rápido em novos chats.
