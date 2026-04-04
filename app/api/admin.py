import html
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_SP_TZ = ZoneInfo("America/Sao_Paulo")

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.memory.session import get_history, get_history_persistent, iter_leads, get_lead, update_lead_field
from app.models.lead import LeadStage
from app.services import whatsapp

logger = structlog.get_logger()
router = APIRouter()


class OutboundTemplateRequest(BaseModel):
    phone_number: str = Field(..., description="Número do lead com DDI (somente números ou formatado)")
    template_name: str = Field(..., description="Nome do template aprovado na Meta")
    language_code: str = Field(default="pt_BR", description="Idioma do template (ex: pt_BR)")
    body_params: list[str] = Field(default_factory=list, description="Parâmetros do body na ordem do template")


class PauseAgentRequest(BaseModel):
    phone_number: str = Field(..., description="Número do lead (com ou sem DDI)")


def _authorize_admin(x_admin_key: str | None, key: str | None = None) -> None:
    token = x_admin_key or key
    if not token or token != settings.app_secret:
        raise HTTPException(status_code=401, detail="Não autorizado")


def _format_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


@router.get("/monitor", response_class=HTMLResponse)
async def admin_monitor_page(
    x_admin_key: str | None = Header(default=None),
    key: str | None = Query(default=None, description="APP_SECRET para acesso via navegador"),
):
    """Painel simples (Fase 1) para visualizar leads em atendimento e conversa em balões."""
    _authorize_admin(x_admin_key, key)

    safe_key = html.escape(key or x_admin_key or "")
    course_options = "\n".join(
        f'<option value="{html.escape(slug)}">{html.escape(slug)}</option>' for slug in settings.course_slugs_list
    )
    page = f"""
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Monitor de Atendimento</title>
  <style>
    :root {{
      --bg: #f3f6fb;
      --panel: #ffffff;
      --line: #e5eaf2;
      --text: #1f2937;
      --muted: #6b7280;
      --brand: #3b82f6;
      --brand-soft: #eff6ff;
      --assistant: #dcfce7;
      --assistant-line: #86efac;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, Arial, sans-serif; background: var(--bg); color: var(--text); overflow:hidden; }}
    /* ── tabs ── */
    .tabs-bar {{ display:flex; background:var(--panel); border-bottom:2px solid var(--line); padding:0 16px; gap:4px; flex-shrink:0; }}
    .tab-btn {{ padding:12px 18px; font-size:13px; font-weight:600; cursor:pointer; border:none; background:none; color:var(--muted); border-bottom:2px solid transparent; margin-bottom:-2px; }}
    .tab-btn.active {{ color:var(--brand); border-bottom-color:var(--brand); }}
    .tab-content {{ display:none; flex:1; overflow:hidden; }}
    .tab-content.active {{ display:flex; flex:1; overflow:hidden; }}
    /* ── monitor ── */
    .app {{ display:grid; grid-template-columns: 320px 1fr; flex:1; overflow:hidden; width:100%; }}
    .page-wrap {{ display:flex; flex-direction:column; height:100vh; overflow:hidden; }}
    .sidebar {{ border-right:1px solid var(--line); background:var(--panel); overflow-y:auto; overflow-x:hidden; display:flex; flex-direction:column; min-height:0; }}
    .chat {{ display:flex; flex-direction:column; min-width:0; min-height:0; overflow:hidden; }}
    .header {{ padding:14px 18px; border-bottom:1px solid var(--line); background:var(--panel); }}
    .header-title {{ font-weight:700; font-size:15px; }}
    .header-meta {{ font-size:12px; color:var(--muted); margin-top:3px; }}
    .toolbar {{ padding:12px; border-bottom:1px solid var(--line); background:var(--panel); position:sticky; top:0; z-index:10; }}
    .toolbar-title {{ font-weight:700; margin-bottom:8px; font-size:14px; }}
    input[type="text"] {{ width:100%; padding:10px 12px; border:1px solid #cfd8e3; border-radius:10px; font-size:14px; }}
    select {{ width:100%; padding:10px 12px; border:1px solid #cfd8e3; border-radius:10px; font-size:14px; background:#fff; }}
    .toolbar-row {{ display:flex; flex-direction:column; gap:8px; }}
    .lead-item {{ padding:12px 14px; border-bottom:1px solid #f0f3f8; cursor:pointer; }}
    .lead-item:hover {{ background:#f8fbff; }}
    .lead-item.active {{ background:var(--brand-soft); border-left:3px solid var(--brand); padding-left:11px; }}
    .name {{ font-weight:700; display:flex; align-items:center; gap:6px; flex:1; min-width:0; }}
    .name-row {{ display:flex; align-items:center; justify-content:space-between; gap:6px; }}
    .last-time {{ font-size:11px; color:var(--muted); white-space:nowrap; flex-shrink:0; }}
    .meta {{ font-size:12px; color:var(--muted); margin-top:4px; }}
    .preview {{ font-size:13px; margin-top:5px; color:#334155; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .tag {{ background:#eef2ff; color:#4338ca; border-radius:999px; font-size:11px; padding:2px 8px; flex-shrink:0; }}
    .tag.escalated {{ background:#fee2e2; color:#b91c1c; }}
    .chat-body {{ flex:1; overflow:auto; padding:10px 12px; display:flex; flex-direction:column; gap:6px; background:#efeae2; }}
    .msg-row {{ display:flex; width:100%; margin:0; }}
    .msg-row.user {{ justify-content:flex-start; }}
    .msg-row.assistant {{ justify-content:flex-end; }}
    .bubble-wrap {{ display:flex; flex-direction:column; max-width:min(58%, 560px); }}
    .msg-row.user .bubble-wrap {{ align-items:flex-start; }}
    .msg-row.assistant .bubble-wrap {{ align-items:flex-end; }}
    .bubble {{ padding:8px 10px; border-radius:8px; line-height:1.4; white-space:pre-wrap; word-break:break-word; overflow-wrap:anywhere; font-size:13px; }}
    .bubble.user {{ background:#ffffff; border:1px solid #e5e7eb; border-top-left-radius:2px; }}
    .bubble.assistant {{ background:#d9fdd3; border:1px solid #b8efae; border-top-right-radius:2px; }}
    .msg-time {{ font-size:10px; color:var(--muted); margin-top:3px; padding:0 2px; }}
    .media-chip {{ display:inline-block; font-size:10px; padding:2px 6px; border-radius:999px; background:#e2e8f0; color:#334155; font-weight:700; margin-bottom:4px; }}
    .empty {{ padding:24px; color:var(--muted); text-align:center; }}
    /* ── relatório ── */
    .report-wrap {{ flex:1; overflow-y:auto; padding:24px; background:var(--bg); }}
    .report-grid {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap:16px; margin-bottom:28px; }}
    .kpi {{ background:var(--panel); border-radius:12px; padding:18px 20px; border:1px solid var(--line); }}
    .kpi-label {{ font-size:12px; color:var(--muted); margin-bottom:6px; font-weight:600; text-transform:uppercase; letter-spacing:.5px; }}
    .kpi-value {{ font-size:28px; font-weight:800; color:var(--text); }}
    .kpi-value.green {{ color:#16a34a; }}
    .kpi-value.red {{ color:#dc2626; }}
    .kpi-value.blue {{ color:var(--brand); }}
    .kpi-sub {{ font-size:12px; color:var(--muted); margin-top:4px; }}
    .section-title {{ font-weight:700; font-size:14px; margin-bottom:12px; color:var(--text); }}
    .chart-row {{ display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-bottom:28px; }}
    .chart-box {{ background:var(--panel); border-radius:12px; padding:20px; border:1px solid var(--line); }}
    .bar-item {{ display:flex; align-items:center; gap:10px; margin-bottom:8px; font-size:13px; }}
    .bar-label {{ width:160px; flex-shrink:0; color:var(--text); }}
    .bar-track {{ flex:1; background:#f1f5f9; border-radius:999px; height:10px; overflow:hidden; }}
    .bar-fill {{ height:100%; border-radius:999px; background:var(--brand); transition:width .4s; }}
    .bar-fill.green {{ background:#22c55e; }}
    .bar-fill.orange {{ background:#f97316; }}
    .bar-count {{ width:36px; text-align:right; font-weight:700; color:var(--muted); font-size:12px; flex-shrink:0; }}
    .report-updated {{ font-size:11px; color:var(--muted); text-align:right; margin-bottom:12px; }}
    /* tooltips */
    .info-icon {{ display:inline-flex; align-items:center; justify-content:center; width:15px; height:15px; border-radius:50%; background:#e2e8f0; color:#64748b; font-size:10px; font-weight:700; cursor:default; margin-left:5px; position:relative; vertical-align:middle; }}
    .info-icon:hover .tooltip {{ display:block; }}
    .tooltip {{ display:none; position:absolute; bottom:calc(100% + 6px); left:50%; transform:translateX(-50%); background:#1e293b; color:#f8fafc; font-size:11px; font-weight:400; padding:6px 10px; border-radius:6px; white-space:nowrap; z-index:100; min-width:180px; max-width:260px; white-space:normal; line-height:1.4; pointer-events:none; }}
    .tooltip::after {{ content:""; position:absolute; top:100%; left:50%; transform:translateX(-50%); border:5px solid transparent; border-top-color:#1e293b; }}
    /* follow-up table */
    .fu-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    .fu-table th {{ text-align:left; padding:6px 10px; color:var(--muted); font-size:11px; font-weight:600; text-transform:uppercase; border-bottom:1px solid var(--line); }}
    .fu-table td {{ padding:7px 10px; border-bottom:1px solid #f1f5f9; }}
    .fu-table tr:last-child td {{ border-bottom:none; }}
    .rate-pill {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:700; }}
    .rate-pill.high {{ background:#dcfce7; color:#15803d; }}
    .rate-pill.mid {{ background:#fef9c3; color:#a16207; }}
    .rate-pill.low {{ background:#fee2e2; color:#b91c1c; }}
    /* report toolbar */
    .report-toolbar {{ display:flex; align-items:center; gap:10px; padding:12px 24px; background:var(--panel); border-bottom:1px solid var(--line); flex-shrink:0; flex-wrap:wrap; }}
    .report-toolbar label {{ font-size:12px; color:var(--muted); font-weight:600; }}
    .report-toolbar input[type="date"] {{ padding:7px 10px; border:1px solid #cfd8e3; border-radius:8px; font-size:13px; color:var(--text); }}
    .btn-refresh {{ padding:8px 18px; background:var(--brand); color:#fff; border:none; border-radius:8px; font-size:13px; font-weight:600; cursor:pointer; margin-left:auto; }}
    .btn-refresh:hover {{ background:#2563eb; }}
    .btn-refresh:disabled {{ background:#93c5fd; cursor:default; }}
    /* abandonment bar */
    .abandon-bar-item {{ display:flex; align-items:center; gap:8px; margin-bottom:9px; font-size:13px; }}
    .abandon-label {{ width:100px; flex-shrink:0; }}
    .abandon-track {{ flex:1; background:#f1f5f9; border-radius:999px; height:10px; overflow:hidden; position:relative; }}
    .abandon-fill {{ height:100%; border-radius:999px; background:#ef4444; transition:width .4s; }}
    .abandon-fill.low {{ background:#22c55e; }}
    .abandon-fill.mid {{ background:#f97316; }}
    .abandon-stats {{ font-size:11px; color:var(--muted); white-space:nowrap; min-width:110px; text-align:right; }}
    /* ── agent control ── */
    .agent-control {{ margin-top:12px; padding:12px; background:#f0f9ff; border-radius:8px; border:1px solid #bfdbfe; }}
    .script-info {{ font-size:12px; color:var(--text); line-height:1.6; margin-bottom:10px; }}
    .script-info div {{ margin:4px 0; }}
    .agent-status {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
    .status-badge {{ font-size:13px; font-weight:600; padding:4px 10px; border-radius:20px; }}
    .status-badge.active {{ background:#dcfce7; color:#15803d; }}
    .status-badge.paused {{ background:#fee2e2; color:#b91c1c; }}
    .btn-agent {{ padding:6px 12px; border:none; border-radius:6px; font-size:12px; font-weight:600; cursor:pointer; background:var(--brand); color:#fff; transition:background .2s; }}
    .btn-agent:hover {{ background:#2563eb; }}
    /* ── followups tab ── */
    .followups-toolbar {{ display:flex; gap:12px; padding:12px 24px; background:var(--panel); border-bottom:1px solid var(--line); align-items:center; justify-content:space-between; flex-wrap:wrap; }}
    .tag-filter {{ padding:6px 12px; border:1px solid #e5eaf2; border-radius:20px; background:#fff; cursor:pointer; font-size:12px; font-weight:600; color:var(--muted); transition:all .2s; }}
    .tag-filter:hover {{ border-color:var(--brand); color:var(--brand); }}
    .tag-filter.active {{ background:var(--brand); color:#fff; border-color:var(--brand); }}
    .followups-list {{ flex:1; overflow-y:auto; padding:24px; background:var(--bg); }}
    .fu-table {{ width:100%; border-collapse:collapse; font-size:13px; margin-bottom:20px; }}
    .fu-table th {{ text-align:left; padding:10px 12px; color:var(--muted); font-size:11px; font-weight:600; text-transform:uppercase; border-bottom:2px solid var(--line); background:var(--panel); }}
    .fu-table td {{ padding:12px; border-bottom:1px solid #f1f5f9; vertical-align:middle; }}
    .fu-table tbody tr:hover {{ background:#f8fbff; }}
    .fu-table tr:last-child td {{ border-bottom:none; }}
    .fu-status-badge {{ display:inline-block; padding:4px 8px; border-radius:4px; font-size:11px; font-weight:600; }}
    .fu-status-badge.pending {{ background:#dbeafe; color:#0c4a6e; }}
    .fu-status-badge.sent {{ background:#dcfce7; color:#15803d; }}
    .fu-status-badge.failed {{ background:#fee2e2; color:#b91c1c; }}
  </style>
</head>
<body>
  <div class="page-wrap">
    <div class="tabs-bar">
      <button class="tab-btn active" onclick="switchTab('monitor')">Conversas</button>
      <button class="tab-btn" onclick="switchTab('followups')">Seguimentos</button>
      <button class="tab-btn" onclick="switchTab('report')">Relatório</button>
    </div>

    <!-- ABA: CONVERSAS -->
    <div class="tab-content active" id="tab-monitor">
      <div class="app">
        <aside class="sidebar">
          <div class="toolbar">
            <div class="toolbar-title">Painel de Atendimento</div>
            <div class="toolbar-row">
              <input id="search" type="text" placeholder="Buscar por nome ou telefone" />
              <select id="productTag">
                <option value="">Todos os produtos</option>
                {course_options}
              </select>
            </div>
          </div>
          <div id="leadList"></div>
        </aside>
        <section class="chat">
          <div class="header">
            <div class="header-title" id="chatHeader">Selecione um lead</div>
            <div class="header-meta" id="chatSubHeader">Histórico em tempo real</div>
            <!-- Agent Control Section -->
            <div class="agent-control" id="agentControl" style="display:none;">
              <div class="script-info" id="scriptInfo">
                <div><strong>📝 Script:</strong> <span id="scriptName">-</span></div>
                <div><strong>📍 Passo:</strong> <span id="scriptStep">0</span> | <strong>Bloco:</strong> <span id="scriptBlock">-</span></div>
              </div>
              <div class="agent-status">
                <span id="agentBadge" class="status-badge active">🟢 Ativo</span>
                <button onclick="pauseAgentForLead()" class="btn-agent" id="pauseBtn">⏸ Pausar</button>
                <button onclick="resumeAgentForLead()" class="btn-agent" id="resumeBtn" style="display:none;">▶ Retomar</button>
              </div>
            </div>
          </div>
          <div class="chat-body" id="chatBody">
            <div class="empty">Sem conversa selecionada.</div>
          </div>
        </section>
      </div>
    </div>

    <!-- ABA: SEGUIMENTOS -->
    <div class="tab-content" id="tab-followups" style="flex-direction:column">
      <div class="followups-toolbar">
        <div style="display:flex; gap:10px; align-items:center;">
          <button class="tag-filter" onclick="filterFollowups('pending')" data-status="pending">✅ Pendente</button>
          <button class="tag-filter" onclick="filterFollowups('sent')" data-status="sent">📤 Enviado</button>
          <button class="tag-filter" onclick="filterFollowups('failed')" data-status="failed">❌ Falhou</button>
        </div>
        <button class="btn-refresh" onclick="loadFollowups()">↻ Atualizar</button>
      </div>
      <div class="followups-list" id="followupsList">
        <div class="empty">Carregando seguimentos...</div>
      </div>
    </div>

    <!-- ABA: RELATÓRIO -->
    <div class="tab-content" id="tab-report" style="flex-direction:column">
      <div class="report-toolbar">
        <label>De</label>
        <input type="date" id="filterFrom" />
        <label>Até</label>
        <input type="date" id="filterTo" />
        <button class="btn-refresh" id="btnRefresh" onclick="loadReport()">↻ Atualizar</button>
        <button class="btn-refresh" style="background:#0f766e" onclick="exportReport()">⬇ Exportar conversas</button>
      </div>
      <div class="report-wrap" id="reportWrap">
        <div class="empty">Abra a aba para carregar o relatório.</div>
      </div>
    </div>
  </div>

<script>
  const adminKey = "{safe_key}";
  let allLeads = [];
  let selectedPhone = null;
  let pauseLiveRefresh = false;

  const SCROLL_STICKY_THRESHOLD_PX = 140;

  const STAGE_PT = {{
    "new": "Novo",
    "identifying": "Identificando",
    "nurturing": "Em atendimento",
    "objection": "Objeção",
    "hot": "Interessado",
    "negotiating": "Negociando",
    "converted": "Convertido",
    "escalated": "Escalado",
    "lost": "Perdido",
  }};

  function stageLabel(stage) {{
    return STAGE_PT[stage] || stage;
  }}

  function esc(text) {{
    return (text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }}

  function fmtTime(iso) {{
    if (!iso) return "";
    // Garante que strings sem fuso (vindo do servidor em UTC) sejam tratadas como UTC
    const isoUtc = iso.endsWith("Z") || /[+-]\d{{2}}:\d{{2}}$/.test(iso) ? iso : iso + "Z";
    const d = new Date(isoUtc);
    if (isNaN(d)) return "";
    return d.toLocaleString("pt-BR", {{
      timeZone: "America/Sao_Paulo",
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }}).replace(",", "");
  }}

  async function loadLeads() {{
    const productTag = document.getElementById("productTag")?.value || "";
    let url = `/admin/monitor/leads?key=${{encodeURIComponent(adminKey)}}`;
    if (productTag) url += `&product_tag=${{encodeURIComponent(productTag)}}`;

    const res = await fetch(url);
    if (!res.ok) {{
      document.getElementById("leadList").innerHTML = `<div class='empty'>Erro ao carregar leads (${{res.status}})</div>`;
      return;
    }}
    const data = await res.json();
    allLeads = data.leads || [];
    renderLeads();
  }}

  function renderLeads() {{
    const q = document.getElementById("search").value.toLowerCase().trim();
    const productTag = document.getElementById("productTag")?.value || "";
    const filtered = allLeads.filter(l =>
      (
        String(l.name || "").toLowerCase().includes(q) ||
        String(l.phone_number || "").toLowerCase().includes(q)
      ) &&
      (!productTag || String(l.course_slug || "") === productTag)
    );

    const htmlLeads = filtered.map(l => `
      <div class="lead-item ${{selectedPhone===l.phone_number ? "active" : ""}}" onclick="openChat('${{l.phone_number}}')">
        <div class="name-row">
          <div class="name">
            <span>${{esc(l.name || "Lead sem nome")}}</span>
            ${{l.is_escalated ? '<span class="tag escalated">🚨 Escalado</span>' : `<span class="tag">${{stageLabel(l.stage)}}</span>`}}
          </div>
          <span class="last-time">${{fmtTime(l.last_inbound_at)}}</span>
        </div>
        <div class="meta">${{esc(l.phone_number)}} • passo ${{l.script_step}}</div>
        <div class="preview">${{esc(l.last_message_preview || "Sem mensagens")}}</div>
      </div>
    `).join("");

    document.getElementById("leadList").innerHTML = htmlLeads || "<div class='empty'>Nenhum lead encontrado.</div>";
  }}

  function bubbleClass(content, role) {{
    const side = role === 'assistant' ? 'assistant' : 'user';
    return `bubble ${{side}}`;
  }}

  function renderContent(content) {{
    const c = String(content ?? "");
    if (c.startsWith("[áudio enviado]")) {{
      return `<span class="media-chip">ÁUDIO</span>\n${{esc(c)}}`;
    }}
    if (c.startsWith("[imagem enviada]")) {{
      return `<span class="media-chip">IMAGEM</span>\n${{esc(c)}}`;
    }}
    if (c.startsWith("[template]")) {{
      return `<span class="media-chip">TEMPLATE</span>\n${{esc(c)}}`;
    }}
    return esc(c);
  }}

  async function openChat(phone, preserveScroll=false) {{
    selectedPhone = phone;
    renderLeads();

    const body = document.getElementById("chatBody");
    const distanceFromBottom = body.scrollHeight - body.scrollTop - body.clientHeight;
    const shouldStickBottom = preserveScroll ? (distanceFromBottom < SCROLL_STICKY_THRESHOLD_PX) : true;
    const prevScrollTop = body.scrollTop;

    const res = await fetch(`/admin/monitor/history/${{encodeURIComponent(phone)}}?key=${{encodeURIComponent(adminKey)}}`);
    if (!res.ok) {{
      document.getElementById("chatBody").innerHTML = `<div class='empty'>Erro ao carregar conversa (${{res.status}})</div>`;
      return;
    }}

    const data = await res.json();
    const lead = data.lead || {{}};
    const messages = data.messages || [];

    document.getElementById("chatHeader").innerText = `${{lead.name || "Lead sem nome"}}`;
    document.getElementById("chatSubHeader").innerText = `${{lead.phone_number || ""}} • ${{lead.course_slug || ""}} • ${{stageLabel(lead.stage || "")}}`;

    if (!messages.length) {{
      document.getElementById("chatBody").innerHTML = "<div class='empty'>Sem histórico para este lead.</div>";
      return;
    }}

    document.getElementById("chatBody").innerHTML = messages.map(m => `
      <div class="msg-row ${{m.role === 'assistant' ? 'assistant' : 'user'}}">
        <div class="bubble-wrap">
          <div class="${{bubbleClass(m.content, m.role)}}">${{renderContent(m.content)}}</div>
          ${{m.timestamp ? `<span class="msg-time">${{fmtTime(m.timestamp)}}</span>` : ""}}
        </div>
      </div>
    `).join("");

    if (shouldStickBottom) {{
      body.scrollTop = body.scrollHeight;
    }} else if (preserveScroll) {{
      // Mantém a posição do usuário ao reler histórico (evita "pular" para o fim).
      body.scrollTop = prevScrollTop;
    }}
  }}

  function refreshOpenChat() {{
    if (selectedPhone) {{
      if (pauseLiveRefresh) return;
      openChat(selectedPhone, true);
    }}
  }}

  // Se o usuário estiver scrollando para ler mensagens antigas, pause o refresh ao vivo.
  // O refresh volta automaticamente quando ele rolar de volta para perto do final.
  document.getElementById("chatBody").addEventListener("scroll", () => {{
    const body = document.getElementById("chatBody");
    const distanceFromBottom = body.scrollHeight - body.scrollTop - body.clientHeight;
    pauseLiveRefresh = distanceFromBottom > SCROLL_STICKY_THRESHOLD_PX;
  }});

  document.getElementById("search").addEventListener("input", renderLeads);
  document.getElementById("productTag").addEventListener("change", () => loadLeads());
  loadLeads();
  setInterval(loadLeads, 10000);
  setInterval(refreshOpenChat, 5000);

  // ── Tabs ──────────────────────────────────────────────────────────────────
  function switchTab(name) {{
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    document.querySelector(`[onclick="switchTab('${{name}}')"]`).classList.add("active");
    document.getElementById(`tab-${{name}}`).classList.add("active");
    if (name === "report") loadReport();
  }}

  // ── Relatório ─────────────────────────────────────────────────────────────
  const STAGE_COLOR = {{
    new: "", identifying: "", nurturing: "blue",
    objection: "orange", hot: "green", negotiating: "green",
    converted: "green", escalated: "orange", lost: "orange",
  }};

  const FU_STATUS_PT = {{
    idle: "Aguardando início", running: "Em execução",
    stopped: "Parado (lead respondeu)", finished: "Sequência concluída", failed: "Falhou",
  }};

  const STAGE_PT_FULL = {{
    new: "Novo (sem contato)", identifying: "Identificando curso",
    nurturing: "Em atendimento", objection: "Com objeção",
    hot: "Interessado", negotiating: "Negociando",
    converted: "Convertido", escalated: "Escalado p/ humano", lost: "Perdido",
  }};

  function tip(text) {{
    return `<span class="info-icon">i<span class="tooltip">${{text}}</span></span>`;
  }}

  function barHtml(label, count, max, colorClass="") {{
    const pct = max > 0 ? Math.round(count / max * 100) : 0;
    return `
      <div class="bar-item">
        <div class="bar-label">${{esc(label)}}</div>
        <div class="bar-track"><div class="bar-fill ${{colorClass}}" style="width:${{pct}}%"></div></div>
        <div class="bar-count">${{count}}</div>
      </div>`;
  }}

  function abandonBarHtml(row) {{
    const rate = row.abandon_rate;
    const cls  = rate <= 20 ? "low" : rate <= 50 ? "mid" : "";
    return `
      <div class="abandon-bar-item">
        <div class="abandon-label">${{esc(row.label)}}</div>
        <div class="abandon-track"><div class="abandon-fill ${{cls}}" style="width:${{rate}}%"></div></div>
        <div class="abandon-stats">${{row.stopped}} parados · ${{rate}}% abandon.</div>
      </div>`;
  }}

  function ratePill(rate) {{
    const cls = rate >= 30 ? "high" : rate >= 10 ? "mid" : "low";
    return `<span class="rate-pill ${{cls}}">${{rate}}%</span>`;
  }}

  function fuTableHtml(rows) {{
    if (!rows || !rows.length) return "<div class='empty' style='padding:12px'>Sem dados ainda</div>";
    return `
      <table class="fu-table">
        <thead><tr>
          <th>Mensagem ${{tip("Timing de envio em relação ao último contato do lead")}}</th>
          <th>Tipo</th>
          <th>Enviado</th>
          <th>Responderam</th>
          <th>Taxa resp. ${{tip("% de leads que responderam após receber esta mensagem")}}</th>
        </tr></thead>
        <tbody>
          ${{rows.map(r => `
            <tr style="${{r.sent === 0 ? "opacity:0.45" : ""}}">
              <td><strong>${{r.label}}</strong></td>
              <td><span style="font-size:10px;padding:1px 6px;border-radius:999px;background:${{r.is_template ? "#ede9fe" : "#e0f2fe"}};color:${{r.is_template ? "#6d28d9" : "#0369a1"}}">${{r.is_template ? "Template" : "Texto livre"}}</span></td>
              <td>${{r.sent}}</td>
              <td>${{r.replied}}</td>
              <td>${{r.sent > 0 ? ratePill(r.reply_rate) : '<span style="color:#ccc;font-size:11px">—</span>'}}</td>
            </tr>
          `).join("")}}
        </tbody>
      </table>`;
  }}

  async function loadReport() {{
    const btn = document.getElementById("btnRefresh");
    if (btn) {{ btn.disabled = true; btn.textContent = "Carregando..."; }}

    const from = document.getElementById("filterFrom")?.value || "";
    const to   = document.getElementById("filterTo")?.value || "";
    let url = `/admin/monitor/stats?key=${{encodeURIComponent(adminKey)}}`;
    if (from) url += `&date_from=${{encodeURIComponent(from)}}`;
    if (to)   url += `&date_to=${{encodeURIComponent(to)}}`;

    const res = await fetch(url);
    if (btn) {{ btn.disabled = false; btn.textContent = "↻ Atualizar"; }}
    if (!res.ok) {{
      document.getElementById("reportWrap").innerHTML = `<div class='empty'>Erro ao carregar relatório (${{res.status}})</div>`;
      return;
    }}
    const s = await res.json();
    const now = new Date().toLocaleString("pt-BR");
    const dateRange = (from || to) ? ` · Período: ${{from || "início"}} → ${{to || "hoje"}}` : " · Todos os períodos";

    const stageMax = Math.max(...Object.values(s.by_stage), 1);
    const fuMax    = Math.max(...Object.values(s.by_followup_status), 1);

    const stageBars = Object.entries(s.by_stage).map(([k, v]) =>
      barHtml(STAGE_PT_FULL[k] || k, v, stageMax, STAGE_COLOR[k] || "")
    ).join("");

    const fuStatusBars = Object.entries(s.by_followup_status).map(([k, v]) =>
      barHtml(FU_STATUS_PT[k] || k, v, fuMax, k === "running" ? "green" : k === "stopped" || k === "failed" ? "orange" : "")
    ).join("");

    const stepBars = (s.by_script_step || []).map(r => abandonBarHtml(r)).join("");

    document.getElementById("reportWrap").innerHTML = `
      <div class="report-updated">Atualizado em ${{now}}${{dateRange}}</div>

      <div class="report-grid">
        <div class="kpi">
          <div class="kpi-label">Total de leads ${{tip("Todos os leads no período selecionado.")}}</div>
          <div class="kpi-value blue">${{s.total_leads}}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Respondidos pelo agente ${{tip("Leads que receberam pelo menos 1 mensagem do agente.")}}</div>
          <div class="kpi-value green">${{s.leads_responded}}</div>
          <div class="kpi-sub">Taxa: ${{s.response_rate}}%</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Sem resposta ${{tip("Leads que entraram em contato mas o agente nunca respondeu.")}}</div>
          <div class="kpi-value red">${{s.leads_no_response}}</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Convertidos ${{tip("Leads com matrícula realizada.")}}</div>
          <div class="kpi-value green">${{s.converted}}</div>
          <div class="kpi-sub">Taxa: ${{s.conversion_rate}}%</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">Escalados ${{tip("Leads encaminhados ao humano via WhatsApp.")}}</div>
          <div class="kpi-value" style="color:#d97706">${{s.escalated}}</div>
        </div>
      </div>

      <div class="chart-row">
        <div class="chart-box">
          <div class="section-title">Distribuição por estágio ${{tip("Onde cada lead está no funil agora.")}}</div>
          ${{stageBars}}
        </div>
        <div class="chart-box">
          <div class="section-title">Status do follow-up ${{tip("Situação atual da régua de follow-up de cada lead.")}}</div>
          ${{fuStatusBars}}
        </div>
      </div>

      <div class="chart-row" style="grid-template-columns:1fr">
        <div class="chart-box">
          <div class="section-title">Taxa de abandono por step do script ${{tip("Para cada etapa: % de leads que chegaram até ela mas pararam aqui. Barra vermelha = alto abandono. Verde = baixo abandono. 'Concluído' = percorreu o script inteiro.")}}</div>
          <div style="display:flex;gap:20px;font-size:11px;color:var(--muted);margin-bottom:12px">
            <span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:50%;background:#22c55e;display:inline-block"></span>≤20% abandono</span>
            <span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:50%;background:#f97316;display:inline-block"></span>20–50%</span>
            <span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:50%;background:#ef4444;display:inline-block"></span>>50%</span>
          </div>
          ${{stepBars || "<div class='empty'>Sem dados</div>"}}
        </div>
      </div>

      <div class="chart-row">
        <div class="chart-box">
          <div class="section-title">Follow-up C1 — Pré-preço ${{tip("Régua enviada antes de revelar o valor. Mostra engajamento por mensagem.")}}</div>
          ${{fuTableHtml(s.followup_c1)}}
        </div>
        <div class="chart-box">
          <div class="section-title">Follow-up C2 — Pós-preço ${{tip("Régua enviada após o lead ver o investimento.")}}</div>
          ${{fuTableHtml(s.followup_c2)}}
        </div>
      </div>
    `;
  }}

  function exportReport() {{
    const from = document.getElementById("filterFrom")?.value || "";
    const to   = document.getElementById("filterTo")?.value || "";
    let url = `/admin/monitor/export?key=${{encodeURIComponent(adminKey)}}`;
    if (from) url += `&date_from=${{encodeURIComponent(from)}}`;
    if (to)   url += `&date_to=${{encodeURIComponent(to)}}`;
    window.location.href = url;
  }}

  // ─────────────────────────────────────
  // Agent Control Functions
  // ─────────────────────────────────────

  async function pauseAgentForLead() {{
    if (!selectedPhone) return alert("Selecione um lead primeiro");

    try {{
      const res = await fetch(`/admin/lead-pause-agent?key=${{encodeURIComponent(adminKey)}}`, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ phone_number: selectedPhone }})
      }});

      if (res.ok) {{
        updateAgentStatus(true);
        console.log("✅ Agent paused for", selectedPhone);
      }} else {{
        alert("Erro ao pausar agente");
      }}
    }} catch (err) {{
      console.error("Error pausing agent:", err);
      alert("Erro ao pausar agente");
    }}
  }}

  async function resumeAgentForLead() {{
    if (!selectedPhone) return alert("Selecione um lead primeiro");

    try {{
      const res = await fetch(`/admin/lead-resume-agent?key=${{encodeURIComponent(adminKey)}}`, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ phone_number: selectedPhone }})
      }});

      if (res.ok) {{
        updateAgentStatus(false);
        console.log("✅ Agent resumed for", selectedPhone);
      }} else {{
        alert("Erro ao retomar agente");
      }}
    }} catch (err) {{
      console.error("Error resuming agent:", err);
      alert("Erro ao retomar agente");
    }}
  }}

  function updateAgentStatus(isPaused) {{
    const badge = document.getElementById("agentBadge");
    const pauseBtn = document.getElementById("pauseBtn");
    const resumeBtn = document.getElementById("resumeBtn");

    if (isPaused) {{
      badge.textContent = "🔴 Pausado";
      badge.className = "status-badge paused";
      pauseBtn.style.display = "none";
      resumeBtn.style.display = "inline-block";
    }} else {{
      badge.textContent = "🟢 Ativo";
      badge.className = "status-badge active";
      pauseBtn.style.display = "inline-block";
      resumeBtn.style.display = "none";
    }}
  }}

  async function loadScriptStatus() {{
    if (!selectedPhone) return;

    try {{
      const res = await fetch(`/admin/lead-script-status?phone_number=${{encodeURIComponent(selectedPhone)}}&key=${{encodeURIComponent(adminKey)}}`);
      if (res.ok) {{
        const data = await res.json();
        document.getElementById("scriptName").textContent = data.current_script || "---";
        document.getElementById("scriptStep").textContent = data.script_step;
        document.getElementById("scriptBlock").textContent = data.last_script_block || "---";
        document.getElementById("agentControl").style.display = "block";
        updateAgentStatus(data.is_paused);
      }}
    }} catch (err) {{
      console.error("Error loading script status:", err);
    }}
  }}

  // ─────────────────────────────────────
  // Followups Functions
  // ─────────────────────────────────────

  let currentFollowupFilter = "pending";

  async function loadFollowups() {{
    try {{
      const res = await fetch(`/admin/followups-scheduled?status=${{currentFollowupFilter}}&sort=date&key=${{encodeURIComponent(adminKey)}}`);
      if (res.ok) {{
        const data = await res.json();
        renderFollowups(data.followups);
      }}
    }} catch (err) {{
      console.error("Error loading followups:", err);
    }}
  }}

  function renderFollowups(followups) {{
    const list = document.getElementById("followupsList");
    if (!followups || followups.length === 0) {{
      list.innerHTML = '<div class="empty">Nenhum seguimento agendado.</div>';
      return;
    }}

    let html = '<table class="fu-table"><thead><tr><th>Lead</th><th>Status</th><th>Agendado para</th><th>Passo</th></tr></thead><tbody>';

    for (const fu of followups) {{
      const date = fu.scheduled_at ? fmtTime(fu.scheduled_at) : "---";
      let statusBadge = "---";

      if (fu.status === 'active' || fu.status === 'waiting' || fu.status === 'pending') {{
        statusBadge = '<span class="fu-status-badge pending">✅ Pendente</span>';
      }} else if (fu.status === 'sent' || fu.status === 'completed') {{
        statusBadge = '<span class="fu-status-badge sent">📤 Enviado</span>';
      }} else if (fu.status === 'failed') {{
        statusBadge = '<span class="fu-status-badge failed">❌ Falhou</span>';
      }}

      html += `<tr>
        <td><strong>${{esc(fu.name || "---")}}</strong><br><span style="font-size:11px;color:var(--muted)">${{esc(fu.phone || "---")}}</span></td>
        <td>${{statusBadge}}</td>
        <td>${{date}}</td>
        <td>Passo ${{fu.followup_step}}</td>
      </tr>`;
    }}

    html += '</tbody></table>';
    list.innerHTML = html;
  }}

  function filterFollowups(status) {{
    currentFollowupFilter = status;

    // Update active button
    document.querySelectorAll(".tag-filter").forEach(btn => {{
      btn.classList.remove("active");
      if (btn.getAttribute("data-status") === status) {{
        btn.classList.add("active");
      }}
    }});

    loadFollowups();
  }}

  // ─────────────────────────────────────
  // Override openChat to load script status
  // ─────────────────────────────────────

  const originalOpenChat = openChat;
  openChat = async function(phone) {{
    originalOpenChat(phone);
    loadScriptStatus();
  }};

  // ─────────────────────────────────────
  // Load followups when switching to followups tab
  // ─────────────────────────────────────

  const originalSwitchTab = switchTab;
  switchTab = function(tabName) {{
    originalSwitchTab(tabName);
    if (tabName === "followups") {{
      loadFollowups();
    }}
  }};

</script>
</body>
</html>
"""
    return HTMLResponse(content=page)


@router.get("/monitor/leads")
async def admin_monitor_leads(
    x_admin_key: str | None = Header(default=None),
    key: str | None = Query(default=None),
    product_tag: str | None = Query(default=None, description="Filtra pelo course_slug (ex.: pos_fisio_neuro)"),
):
    """Lista leads em atendimento com preview da última mensagem (dados do Redis)."""
    _authorize_admin(x_admin_key, key)

    leads_payload: list[dict] = []
    product_tag_norm = (product_tag or "").strip()

    async for lead in iter_leads():
        if lead.stage in {LeadStage.CONVERTED, LeadStage.LOST}:
            continue
        if product_tag_norm and lead.course_slug.value != product_tag_norm:
            continue

        history = await get_history(lead.phone_number, last_n=1)
        last_msg_raw = history[-1].get("content", "") if history else ""
        last_msg = last_msg_raw if isinstance(last_msg_raw, str) else str(last_msg_raw)

        leads_payload.append(
            {
                "phone_number": lead.phone_number,
                "name": lead.name,
                "course_slug": lead.course_slug.value,
                "stage": lead.stage.value,
                "script_step": lead.script_step,
                "is_escalated": lead.is_escalated,
                "followup_status": lead.followup_status,
                "last_inbound_at": _format_dt(lead.last_inbound_at),
                "last_message_preview": (last_msg[:120] + "...") if len(last_msg) > 120 else last_msg,
            }
        )

    leads_payload.sort(
        key=lambda item: (
            item.get("is_escalated", False),
            item.get("followup_status") == "running",
            item.get("last_inbound_at") or "",
        ),
        reverse=True,
    )

    return {"count": len(leads_payload), "leads": leads_payload}


@router.get("/monitor/history/{phone_number}")
async def admin_monitor_history(
    phone_number: str,
    x_admin_key: str | None = Header(default=None),
    key: str | None = Query(default=None),
):
    """Retorna histórico completo de um lead em formato simples para UI em balões."""
    _authorize_admin(x_admin_key, key)

    clean_phone = "".join(ch for ch in phone_number if ch.isdigit())
    lead_found = None

    async for lead in iter_leads():
        if lead.phone_number == clean_phone:
            lead_found = lead
            break

    if lead_found is None:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    history = await get_history_persistent(clean_phone, last_n=500)
    if not history:
        history = await get_history(clean_phone, last_n=200)

    normalized_history = []
    for m in history:
        content = m.get("content") if isinstance(m, dict) else ""
        normalized_history.append(
            {
                "role": (m.get("role") if isinstance(m, dict) else "") or "user",
                "content": content if isinstance(content, str) else str(content or ""),
                "timestamp": (m.get("timestamp") if isinstance(m, dict) else None),
            }
        )

    return {
        "lead": {
            "phone_number": lead_found.phone_number,
            "name": lead_found.name,
            "stage": lead_found.stage.value,
            "course_slug": lead_found.course_slug.value,
            "script_step": lead_found.script_step,
        },
        "messages": normalized_history,
    }


@router.get("/monitor/stats")
async def admin_monitor_stats(
    x_admin_key: str | None = Header(default=None),
    key: str | None = Query(default=None),
    date_from: str | None = Query(default=None, description="Filtro início (YYYY-MM-DD)"),
    date_to: str | None = Query(default=None, description="Filtro fim (YYYY-MM-DD)"),
):
    """Retorna métricas agregadas de conversas para o painel de relatório."""
    _authorize_admin(x_admin_key, key)

    from collections import defaultdict
    from app.db.database import AsyncSessionLocal
    from app.db.orm_models import ConversationORM
    from sqlalchemy import select
    from app.followup.service import (
        SCENARIO_PRE_PRICE, SCENARIO_POST_PRICE,
        C1_FREE, C2_FREE, C1_TEMPLATE_NAMES, C2_TEMPLATE_NAMES,
        _normalize_scenario,
    )
    from app.script.schedules.pos_fisio_neuro_script import POS_FISIO_NEURO_SCRIPT
    from datetime import timezone

    MAX_SCRIPT_STEP = len(POS_FISIO_NEURO_SCRIPT)  # 19 = script concluído

    # Timings de cada step por cenário
    C1_TIMINGS = ["2h", "3h", "6h", "12h", "20h", "D+1", "D+2", "D+3", "D+4"]
    C2_TIMINGS = ["1h", "3h", "6h", "12h", "20h", "D+1", "D+2", "D+3", "D+4", "D+5", "D+6", "D+7", "D+8"]

    # ── Filtro de datas ──────────────────────────────────────────────────────
    def _parse_date(s: str | None, end_of_day: bool = False):
        if not s:
            return None
        try:
            d = datetime.fromisoformat(s)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if end_of_day:
                from datetime import timedelta
                d = d.replace(hour=23, minute=59, second=59)
            return d
        except ValueError:
            return None

    dt_from = _parse_date(date_from)
    dt_to   = _parse_date(date_to, end_of_day=True)

    def _in_range(lead) -> bool:
        if dt_from is None and dt_to is None:
            return True
        ref = lead.last_inbound_at
        if ref is None:
            return False
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        if dt_from and ref < dt_from:
            return False
        if dt_to and ref > dt_to:
            return False
        return True

    # ── Coleta todos os leads ────────────────────────────────────────────────
    all_leads = [lead async for lead in iter_leads() if _in_range(lead)]
    total = len(all_leads)

    # ── Por estágio ──────────────────────────────────────────────────────────
    by_stage: dict[str, int] = defaultdict(int)
    for lead in all_leads:
        by_stage[lead.stage.value] += 1

    # ── Por status do follow-up ──────────────────────────────────────────────
    by_fu_status: dict[str, int] = defaultdict(int)
    for lead in all_leads:
        fu = lead.followup_status or "idle"
        by_fu_status[fu] += 1

    # ── Abandono por step do script ──────────────────────────────────────────
    # "Chegou ao step N" = leads com script_step >= N (passaram por ele)
    # "Parou no step N" = leads com script_step == N (ficaram aqui)
    # Taxa de abandono = parou_no_step / chegou_ao_step * 100
    by_script_step: list[dict] = []
    for step_n in range(MAX_SCRIPT_STEP + 1):
        label = "Concluído" if step_n >= MAX_SCRIPT_STEP else f"Step {step_n}"
        stopped = sum(1 for l in all_leads if l.script_step == step_n)
        reached = sum(1 for l in all_leads if l.script_step >= step_n)
        if reached == 0:
            continue
        abandon_rate = round(stopped / reached * 100, 1)
        by_script_step.append({
            "label": label,
            "stopped": stopped,
            "reached": reached,
            "abandon_rate": abandon_rate,
        })

    # ── Escalados / convertidos ──────────────────────────────────────────────
    escalated = sum(1 for l in all_leads if l.is_escalated)
    converted = by_stage.get("converted", 0)
    conversion_rate = round(converted / total * 100, 1) if total else 0

    # ── Leads que receberam pelo menos 1 resposta do agente ─────────────────
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ConversationORM.phone_number)
                .where(ConversationORM.role == "assistant")
                .distinct()
            )
            phones_with_response = {row[0] for row in result.fetchall()}
    except Exception:
        phones_with_response = set()

    leads_responded = sum(1 for l in all_leads if l.phone_number in phones_with_response)
    leads_no_response = total - leads_responded
    response_rate = round(leads_responded / total * 100, 1) if total else 0

    # ── Follow-up por mensagem: enviado vs respondeu (por cenário) ───────────
    # followup_step = próximo step a enviar (step N já foi enviado quando followup_step > N)
    # "Respondeu no step N" = lead interrompeu quando followup_step == N+1 e reason = lead_replied
    fu_c1: list[dict] = []
    fu_c2: list[dict] = []

    for scenario_key, timings, fu_list in [
        (SCENARIO_PRE_PRICE, C1_TIMINGS, fu_c1),
        (SCENARIO_POST_PRICE, C2_TIMINGS, fu_c2),
    ]:
        for step_idx, timing in enumerate(timings):
            # Leads com este cenário que passaram pelo step (followup_step > step_idx)
            sent = sum(
                1 for l in all_leads
                if _normalize_scenario(l.followup_scenario, l) == scenario_key
                and (l.followup_status or "idle") != "idle"
                and l.followup_step > step_idx
            )
            # Leads que responderam logo após este step
            replied = sum(
                1 for l in all_leads
                if _normalize_scenario(l.followup_scenario, l) == scenario_key
                and l.followup_step == step_idx + 1
                and l.followup_stopped_reason == "lead_replied"
            )
            fu_list.append({
                "step": step_idx,
                "label": timing,
                "sent": sent,
                "replied": replied,
                "reply_rate": round(replied / sent * 100, 1) if sent else 0,
                "is_template": step_idx >= 5,
            })

    return {
        "total_leads": total,
        "leads_responded": leads_responded,
        "leads_no_response": leads_no_response,
        "response_rate": response_rate,
        "converted": converted,
        "conversion_rate": conversion_rate,
        "escalated": escalated,
        "by_stage": dict(sorted(by_stage.items())),
        "by_followup_status": dict(sorted(by_fu_status.items())),
        "by_script_step": by_script_step,
        "followup_c1": fu_c1,
        "followup_c2": fu_c2,
    }


@router.get("/monitor/export")
async def admin_export_conversations(
    x_admin_key: str | None = Header(default=None),
    key: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
):
    """Gera relatório de conversas em texto plano, filtrável por data."""
    _authorize_admin(x_admin_key, key)

    def _parse_dt(s: str | None, end_of_day: bool = False) -> datetime | None:
        if not s:
            return None
        try:
            d = datetime.fromisoformat(s)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if end_of_day:
                d = d.replace(hour=23, minute=59, second=59)
            return d
        except ValueError:
            return None

    def _fmt(dt: datetime | None) -> str:
        if not dt:
            return "-"
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_SP_TZ).strftime("%d/%m/%Y %H:%M")

    dt_from = _parse_dt(date_from)
    dt_to   = _parse_dt(date_to, end_of_day=True)

    def _in_range(lead) -> bool:
        if dt_from is None and dt_to is None:
            return True
        ref = lead.last_inbound_at
        if ref is None:
            return False
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        if dt_from and ref < dt_from:
            return False
        if dt_to and ref > dt_to:
            return False
        return True

    all_leads = [lead async for lead in iter_leads() if _in_range(lead)]
    all_leads.sort(
        key=lambda l: (l.last_inbound_at or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
    period  = f"{date_from or 'início'} → {date_to or 'hoje'}" if (date_from or date_to) else "Todos os períodos"

    lines: list[str] = []
    lines.append("=" * 80)
    lines.append(f"RELATÓRIO DE CONVERSAS — gerado em {now_str} UTC")
    lines.append(f"Período: {period}  |  Total de leads: {len(all_leads)}")
    lines.append("=" * 80)

    for idx, lead in enumerate(all_leads, start=1):
        history = await get_history_persistent(lead.phone_number, last_n=1000)
        if not history:
            history = await get_history(lead.phone_number, last_n=200)

        price_sent = "sim" if lead.price_sent_at else "não"
        scenario   = lead.followup_scenario or "-"

        lines.append("")
        lines.append("-" * 80)
        lines.append(f"LEAD: {lead.name or '(sem nome)'}  |  {lead.phone_number}")
        lines.append(
            f"Estágio: {lead.stage.value}  |  Script step: {lead.script_step}  |  Preço enviado: {price_sent}"
        )
        lines.append(
            f"Follow-up: {lead.followup_status or 'idle'}  |  Step FU: {lead.followup_step}  |  Cenário: {scenario}"
        )
        lines.append(f"Último inbound: {_fmt(lead.last_inbound_at)}")
        lines.append(f"Total de mensagens: {len(history)}")
        lines.append("")

        if not history:
            lines.append("  (sem mensagens registradas)")
        else:
            for msg in history:
                role    = "LEAD     " if msg.get("role") == "user" else "AGENTE   "
                ts_raw  = msg.get("timestamp")
                if ts_raw:
                    try:
                        ts_dt = datetime.fromisoformat(ts_raw)
                        if ts_dt.tzinfo is None:
                            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
                        ts = ts_dt.astimezone(_SP_TZ).strftime("%d/%m %H:%M")
                    except Exception:
                        ts = "??/??"
                else:
                    ts = "??/??"
                content = (msg.get("content") or "").strip()
                for i, part in enumerate(content.splitlines()):
                    prefix = f"  [{ts}] {role}: " if i == 0 else " " * (len(ts) + 14)
                    lines.append(f"{prefix}{part}")

    lines.append("")
    lines.append("=" * 80)
    lines.append("FIM DO RELATÓRIO")
    lines.append("=" * 80)

    filename = f"conversas_{date_from or 'tudo'}_{date_to or 'hoje'}.txt"
    return PlainTextResponse(
        content="\n".join(lines),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/outbound/template")
async def send_outbound_template(payload: OutboundTemplateRequest, x_admin_key: str | None = Header(default=None)):
    """
    Dispara template outbound (fora da janela de 24h).
    Protegido por header X-Admin-Key (valor = APP_SECRET).
    """
    _authorize_admin(x_admin_key)

    response = await whatsapp.send_template(
        to=payload.phone_number,
        template_name=payload.template_name,
        language_code=payload.language_code,
        body_params=payload.body_params,
    )

    logger.info(
        "📨 Disparo outbound solicitado.",
        phone=payload.phone_number,
        template=payload.template_name,
    )

    return {
        "status": "sent",
        "to": payload.phone_number,
        "template": payload.template_name,
        "meta_response": response,
    }


# ─────────────────────────────────────────
# AGENT CONTROL ENDPOINTS (Pausa/Retoma)
# ─────────────────────────────────────────


@router.post("/lead-pause-agent")
async def pause_agent_for_lead(
    payload: PauseAgentRequest,
    x_admin_key: str | None = Header(default=None),
    key: str | None = Query(default=None),
):
    """Pausar agente para um lead específico."""
    _authorize_admin(x_admin_key, key)

    phone = payload.phone_number
    lead = await get_lead(phone)

    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {phone} não encontrado")

    await update_lead_field(phone, agent_paused=True)
    logger.info(f"⏸ Agent paused for {phone}")

    return {
        "status": "paused",
        "phone": phone,
        "name": lead.name,
        "message": "Agente pausado para este lead",
    }


@router.post("/lead-resume-agent")
async def resume_agent_for_lead(
    payload: PauseAgentRequest,
    x_admin_key: str | None = Header(default=None),
    key: str | None = Query(default=None),
):
    """Retomar agente para um lead específico."""
    _authorize_admin(x_admin_key, key)

    phone = payload.phone_number
    lead = await get_lead(phone)

    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {phone} não encontrado")

    await update_lead_field(phone, agent_paused=False)
    logger.info(f"▶ Agent resumed for {phone}")

    return {
        "status": "resumed",
        "phone": phone,
        "name": lead.name,
        "message": "Agente retomado para este lead",
    }


@router.get("/lead-script-status")
async def get_script_status(
    phone_number: str = Query(..., description="Número do lead"),
    x_admin_key: str | None = Header(default=None),
    key: str | None = Query(default=None),
):
    """Obter status do script em execução para um lead."""
    _authorize_admin(x_admin_key, key)

    lead = await get_lead(phone_number)

    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {phone_number} não encontrado")

    return {
        "phone": phone_number,
        "name": lead.name,
        "course_slug": lead.course_slug,
        "current_script": lead.course_slug,
        "script_step": lead.script_step,
        "last_script_block": lead.last_script_block,
        "is_paused": lead.agent_paused,
        "stage": lead.stage,
    }


@router.get("/followups-scheduled")
async def get_scheduled_followups(
    status: str = Query(default="pending", description="pending|sent|failed"),
    sort: str = Query(default="date", description="date|name|phone"),
    x_admin_key: str | None = Header(default=None),
    key: str | None = Query(default=None),
):
    """
    Listar mensagens agendadas/followups.
    Retorna followups pendentes, enviados ou falhados.
    """
    _authorize_admin(x_admin_key, key)

    followups = []
    for lead in iter_leads():
        if not lead:
            continue

        fu_status = lead.followup_status or "idle"
        fu_next_at = lead.followup_next_at

        # Filtrar por status
        if status == "pending" and fu_status not in ["active", "waiting"]:
            continue
        if status == "sent" and fu_status != "completed":
            continue
        if status == "failed" and fu_status != "failed":
            continue

        if fu_status in ["active", "waiting", "completed", "failed"]:
            followups.append({
                "phone": lead.phone_number,
                "name": lead.name,
                "status": fu_status,
                "scheduled_at": fu_next_at.isoformat() if fu_next_at else None,
                "followup_step": lead.followup_step,
                "followup_scenario": lead.followup_scenario,
            })

    # Ordenar
    if sort == "date":
        followups.sort(key=lambda x: x["scheduled_at"] or "", reverse=False)
    elif sort == "name":
        followups.sort(key=lambda x: x["name"] or "")
    elif sort == "phone":
        followups.sort(key=lambda x: x["phone"])

    return {
        "total": len(followups),
        "filtered_status": status,
        "followups": followups,
    }
