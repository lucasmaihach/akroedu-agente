# Melhorias do Dashboard - Fase 1: Pausar/Retomar Agente

## ✅ Backend Implementado

### Endpoints Criados:
```
POST /admin/lead-pause-agent
  Body: { "phone_number": "5511999999999" }
  Response: { "status": "paused", "phone": "...", "name": "...", "message": "..." }

POST /admin/lead-resume-agent
  Body: { "phone_number": "5511999999999" }
  Response: { "status": "resumed", "phone": "...", "name": "...", "message": "..." }

GET /admin/lead-script-status?phone_number=5511999999999
  Response: { "phone": "...", "name": "...", "course_slug": "...", "script_step": N, "is_paused": bool, ... }

GET /admin/followups-scheduled?status=pending&sort=date
  Response: { "total": N, "filtered_status": "...", "followups": [...] }
```

### Banco de Dados:
- ✅ Migration criada: `20260330_01_add_agent_controls.py`
- ✅ Campos adicionados à tabela `leads`:
  - `agent_paused` (BOOLEAN, default=FALSE, indexed)
  - `last_script_block` (VARCHAR(255), nullable, indexed)

### ORM Model:
- ✅ Campos adicionados em `app/db/orm_models.py`

### Engine:
- ✅ Verificação de pausa adicionada em `app/script/engine.py` no início de `run_script_step()`

---

## 🎨 Frontend: Próximas Alterações Necessárias

### 1. Atualizar Header da Conversa
Na seção `.header` do dashboard, adicionar status e botões de controle:

```html
<div class="header">
  <div class="header-title" id="chatHeader">Selecione um lead</div>
  <div class="header-meta" id="chatSubHeader">Histórico em tempo real</div>
  <!-- NOVO: Status do agente -->
  <div class="agent-status" id="agentStatus" style="display:none;">
    <span id="agentBadge">🟢 Ativo</span>
    <button onclick="pauseAgentForLead()" class="btn-agent">⏸ Pausar</button>
    <button onclick="resumeAgentForLead()" class="btn-agent" id="resumeBtn" style="display:none;">▶ Retomar</button>
  </div>
</div>
```

### 2. Adicionar Nova Aba: "Seguimentos"
```html
<div class="tabs-bar">
  <button class="tab-btn active" onclick="switchTab('monitor')">Conversas</button>
  <button class="tab-btn" onclick="switchTab('followups')">Seguimentos</button>
  <button class="tab-btn" onclick="switchTab('report')">Relatório</button>
</div>

<!-- ABA: SEGUIMENTOS -->
<div class="tab-content" id="tab-followups" style="flex-direction:column">
  <div class="followups-toolbar">
    <div style="display:flex; gap:10px; align-items:center;">
      <button class="tag-filter" onclick="filterFollowups('pending')">✅ Pendente</button>
      <button class="tag-filter" onclick="filterFollowups('sent')">📤 Enviado</button>
      <button class="tag-filter" onclick="filterFollowups('failed')">❌ Falhou</button>
    </div>
    <button class="btn-refresh" onclick="loadFollowups()">↻ Atualizar</button>
  </div>
  <div class="followups-list" id="followupsList">
    <div class="empty">Carregando seguimentos...</div>
  </div>
</div>
```

### 3. Adicionar Script Block Info na Conversa
Mostrar qual bloco do script está sendo executado:

```html
<!-- Dentro de .header ou .toolbar -->
<div class="script-info" id="scriptInfo" style="display:none;">
  <div style="font-size: 12px; color: #666; margin-top: 8px;">
    <strong>Script:</strong> <span id="scriptName">-</span> | 
    <strong>Passo:</strong> <span id="scriptStep">0</span> | 
    <strong>Bloco:</strong> <span id="scriptBlock">-</span>
  </div>
</div>
```

---

## JavaScript Necessário

Adicionar no `<script>` do monitor:

```javascript
// Pausar agente
async function pauseAgentForLead() {
  if (!selectedPhone) return;
  
  const res = await fetch(`/admin/lead-pause-agent?key=${adminKey}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone_number: selectedPhone })
  });
  
  const data = await res.json();
  if (res.ok) {
    updateAgentStatus(true);
    logger.info("Agent paused");
  }
}

// Retomar agente
async function resumeAgentForLead() {
  if (!selectedPhone) return;
  
  const res = await fetch(`/admin/lead-resume-agent?key=${adminKey}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone_number: selectedPhone })
  });
  
  const data = await res.json();
  if (res.ok) {
    updateAgentStatus(false);
    logger.info("Agent resumed");
  }
}

// Atualizar status visual
function updateAgentStatus(isPaused) {
  const badge = document.getElementById("agentBadge");
  const pauseBtn = document.querySelector("button[onclick='pauseAgentForLead()']");
  const resumeBtn = document.getElementById("resumeBtn");
  
  if (isPaused) {
    badge.textContent = "🔴 Pausado";
    pauseBtn.style.display = "none";
    resumeBtn.style.display = "inline";
  } else {
    badge.textContent = "🟢 Ativo";
    pauseBtn.style.display = "inline";
    resumeBtn.style.display = "none";
  }
}

// Carregar status do script
async function loadScriptStatus() {
  if (!selectedPhone) return;
  
  const res = await fetch(`/admin/lead-script-status?phone_number=${selectedPhone}&key=${adminKey}`);
  if (res.ok) {
    const data = await res.json();
    document.getElementById("scriptName").textContent = data.current_script || "---";
    document.getElementById("scriptStep").textContent = data.script_step;
    document.getElementById("scriptBlock").textContent = data.last_script_block || "---";
    document.getElementById("scriptInfo").style.display = "block";
    updateAgentStatus(data.is_paused);
  }
}

// Carregar seguimentos agendados
async function loadFollowups() {
  const res = await fetch(`/admin/followups-scheduled?sort=date&key=${adminKey}`);
  if (res.ok) {
    const data = await res.json();
    renderFollowups(data.followups);
  }
}

// Renderizar lista de seguimentos
function renderFollowups(followups) {
  const list = document.getElementById("followupsList");
  if (followups.length === 0) {
    list.innerHTML = '<div class="empty">Nenhum seguimento agendado.</div>';
    return;
  }
  
  let html = '<table class="fu-table"><thead><tr><th>Lead</th><th>Status</th><th>Agendado para</th><th>Ações</th></tr></thead><tbody>';
  
  for (const fu of followups) {
    const date = new Date(fu.scheduled_at).toLocaleString('pt-BR');
    const statusBadge = fu.status === 'pending' ? '✅ Pendente' : 
                        fu.status === 'sent' ? '📤 Enviado' : '❌ Falhou';
    
    html += `<tr>
      <td>${fu.name}</td>
      <td>${statusBadge}</td>
      <td>${date}</td>
      <td><button onclick="alert('Ações em desenvolvimento')">...</button></td>
    </tr>`;
  }
  
  html += '</tbody></table>';
  list.innerHTML = html;
}

// Filtrar seguimentos por status
function filterFollowups(status) {
  // TODO: Implementar filtro local ou chamar API com filtro
  loadFollowups();
}

// Ao selecionar um lead, carregar status do script
// (integrar com código existente de seleção de lead)
const originalSelectLead = selectLead;
selectLead = async function(phone) {
  originalSelectLead(phone);
  loadScriptStatus();
}
```

---

## CSS Necessário

Adicionar aos estilos:

```css
/* Agent status badge and buttons */
.agent-status {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  padding: 8px;
  background: #f0f9ff;
  border-radius: 8px;
}

#agentBadge {
  font-size: 13px;
  font-weight: 600;
}

.btn-agent {
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  background: #3b82f6;
  color: #fff;
}

.btn-agent:hover {
  background: #2563eb;
}

/* Script info */
.script-info {
  padding: 8px 12px;
  background: #f0f3f8;
  border-radius: 6px;
  font-size: 12px;
}

/* Followups toolbar */
.followups-toolbar {
  display: flex;
  gap: 12px;
  padding: 12px 24px;
  background: var(--panel);
  border-bottom: 1px solid var(--line);
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
}

.tag-filter {
  padding: 6px 12px;
  border: 1px solid #e5eaf2;
  border-radius: 20px;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
}

.tag-filter:hover {
  border-color: #3b82f6;
  color: #3b82f6;
}

.followups-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
```

---

## Teste Manual

1. **Abrir dashboard**: http://localhost:8000/admin/monitor?key=YOUR_SECRET
2. **Selecionar um lead** que tenha script em execução
3. **Verificar status**:
   - Badge mostra "🟢 Ativo" ou "🔴 Pausado"
   - Script info mostra bloco atual
4. **Pausar agente**: Clicar em "⏸ Pausar"
   - Badge muda para "🔴 Pausado"
   - Botão muda para "▶ Retomar"
   - Agent NÃO envia mais mensagens para este lead
5. **Retomar agente**: Clicar em "▶ Retomar"
   - Badge volta para "🟢 Ativo"
   - Agent volta a enviar mensagens normalmente
6. **Aba Seguimentos**: Clique na aba para ver lista de followups agendados

---

## Integração com Admin.py

Para integrar o JavaScript ao dashboard existente, procure por:

```python
page = f"""
<!doctype html>
<html lang="pt-BR">
  ...
  <!-- Adicionar dentro do <script> section -->
```

E insira o JavaScript acima dentro das tags `<script>`.

---

## Próximas Fases

- **Fase 2**: Melhorar visualização de script (mostrar descrição do bloco, próxima ação esperada)
- **Fase 3**: Adicionar funcionalidades na aba de seguimentos (reenviar agora, cancelar, editar hora)
- **Fase 4**: Adicionar logs de ações (quem pausou, quando, por quanto tempo)

