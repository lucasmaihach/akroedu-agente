# Roadmap: Novas Funcionalidades do Dashboard

## 1. Visualizar Bloco do Script em Execução

### O que será adicionado:
- Exibir qual script/bloco está sendo executado para o lead selecionado
- Mostrar contexto do bloco (nome, descrição, próxima ação)
- Indicador visual de progresso no script

### Arquivos a modificar:
- `app/api/admin.py` - Adicionar endpoint `/admin/lead-script-status`
- `app/models/lead.py` - Adicionar campo para rastrear script atual
- HTML/JS do dashboard - Mostrar bloco de script na interface

---

## 2. Pausar e Retomar Agente

### O que será adicionado:
- Botão "Pausar Bot" na conversa do lead
- Botão "Retomar Bot" quando pausado
- Status visual (🟢 Ativo / 🔴 Pausado)
- Impedir que o agente envie mensagens enquanto pausado

### Arquivos a modificar:
- `app/api/admin.py` - Endpoints para pausar/retomar
- `app/memory/session.py` - Adicionar lock/status de pausa
- `app/script/engine.py` - Verificar status de pausa antes de executar
- `app/db/orm_models.py` - Campo `agent_paused` na tabela leads

---

## 3. Aba: Mensagens Agendadas (Followups)

### O que será adicionado:
- Nova aba "Seguimentos" no painel
- Listar todos os followups/mensagens agendadas
- Mostrar: lead, mensagem, data/hora agendada, status (pendente, enviado, falhado)
- Opções: Reenviar agora, Cancelar seguimento, Editar hora

### Arquivos a modificar:
- `app/api/admin.py` - Endpoint `/admin/followups-scheduled`
- `app/followup/service.py` - Métodos para listar, rescindir, resenviar
- HTML/JS do dashboard - Criar aba de followups

---

## Sequência de Implementação (Recomendada)

1. **Fase 1**: Pausar/Retomar (mais simples, impacto imediato)
2. **Fase 2**: Visualizar Script em Execução
3. **Fase 3**: Aba de Mensagens Agendadas

---

## Endpoints Propostos

### Pausar/Retomar Agente
```
POST /admin/lead-pause-agent
Body: { "phone_number": "5511999999999" }
Response: { "paused": true, "status": "Agent paused for this lead" }

POST /admin/lead-resume-agent
Body: { "phone_number": "5511999999999" }
Response: { "paused": false, "status": "Agent resumed for this lead" }
```

### Status do Script
```
GET /admin/lead-script-status?phone_number=5511999999999
Response: {
  "phone": "5511999999999",
  "current_script": "curso_1",
  "current_block": 3,
  "block_name": "Apresentação do Curso",
  "block_description": "Descrição detalhada do programa...",
  "is_paused": false,
  "next_step": "Aguardando resposta do lead"
}
```

### Listar Followups Agendados
```
GET /admin/followups-scheduled?sort=date&status=pending
Response: {
  "followups": [
    {
      "id": "fu_123",
      "lead_phone": "5511999999999",
      "lead_name": "Maria Silva",
      "message": "Olá Maria, tudo bem? Gostaria de..."
      "scheduled_at": "2026-04-02T14:30:00-03:00",
      "status": "pending",
      "type": "followup"
    }
  ]
}
```

---

## Arquitetura Sugerida

### Banco de Dados (Migrations)
```sql
-- Adicionar campo de pausa
ALTER TABLE leads ADD COLUMN agent_paused BOOLEAN DEFAULT FALSE;

-- Adicionar índice
CREATE INDEX idx_agent_paused ON leads(agent_paused);
```

### ORM Model Update
```python
# app/db/orm_models.py
class LeadORM(Base):
    # ... campos existentes ...
    agent_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    last_script_block: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

### Session Module Update
```python
# app/memory/session.py
async def pause_agent(phone: str) -> None:
    """Pausar execução do agente para um lead"""
    
async def resume_agent(phone: str) -> None:
    """Retomar execução do agente para um lead"""
    
async def get_agent_paused_status(phone: str) -> bool:
    """Verificar se agente está pausado"""
```

### Engine Check
```python
# app/script/engine.py - No início de async def dispatch_for_lead()
async def dispatch_for_lead(lead: Lead) -> None:
    # ✅ Verificar se está pausado
    if await get_agent_paused_status(lead.phone):
        logger.info(f"Agent paused for {lead.phone}")
        return
    
    # ... resto da execução ...
```

---

## UI/UX Improvements

### Layout da Aba Conversas
```
┌─────────────────────────────────────────┐
│ Painel | [Conversas] | [Seguimentos] | [Relatório]
├─────────────────────────────────────────┤
│ [Search] │ Seu Nome                      │
│ ─────── │ ┌──────────────────────────┐   │
│ Lead 1  │ │ 🟢 Ativo / 🔴 Pausado    │   │
│ Lead 2  │ │ [⏸ Pausar] [▶ Retomar]   │   │
│ Lead 3  │ │ ─────────────────────────│   │
│         │ │ Script: Curso 1           │   │
│         │ │ Bloco: 3/7 Apresentação  │   │
│         │ │ ─────────────────────────│   │
│         │ │ Mensagens...             │   │
```

### Layout da Aba Seguimentos
```
┌─────────────────────────────────────────┐
│ [Conversas] | [Seguimentos] | [Relatório]
├─────────────────────────────────────────┤
│ Status: [✅ Pendente] [📤 Enviado] [❌ Falhou] │
│ ─────────────────────────────────────────│
│ Maria Silva          | 02/04 14:30  | ⋮ │
│ João Santos          | 03/04 10:00  | ⋮ │
│ Carol Oliveira       | 04/04 16:45  | ⋮ │
│ (+ 12 seguimentos)   |              |   │
└─────────────────────────────────────────┘
```

---

## Próximos Passos
1. Executar a migration para adicionar coluna `agent_paused`
2. Implementar Fase 1: Pausar/Retomar
3. Testar com leads reais
4. Feedback e ajustes
5. Implementar Fase 2 e 3
