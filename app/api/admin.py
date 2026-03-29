import html
from datetime import datetime

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.memory.session import get_history, get_history_persistent, iter_leads
from app.models.lead import LeadStage
from app.services import whatsapp

logger = structlog.get_logger()
router = APIRouter()


class OutboundTemplateRequest(BaseModel):
    phone_number: str = Field(..., description="Número do lead com DDI (somente números ou formatado)")
    template_name: str = Field(..., description="Nome do template aprovado na Meta")
    language_code: str = Field(default="pt_BR", description="Idioma do template (ex: pt_BR)")
    body_params: list[str] = Field(default_factory=list, description="Parâmetros do body na ordem do template")


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
  </style>
</head>
<body>
  <div class="page-wrap">
    <div class="tabs-bar">
      <button class="tab-btn active" onclick="switchTab('monitor')">Conversas</button>
      <button class="tab-btn" onclick="switchTab('report')">Relatório</button>
    </div>

    <!-- ABA: CONVERSAS -->
    <div class="tab-content active" id="tab-monitor">
      <div class="app">
        <aside class="sidebar">
          <div class="toolbar">
            <div class="toolbar-title">Painel de Atendimento</div>
            <input id="search" type="text" placeholder="Buscar por nome ou telefone" />
          </div>
          <div id="leadList"></div>
        </aside>
        <section class="chat">
          <div class="header">
            <div class="header-title" id="chatHeader">Selecione um lead</div>
            <div class="header-meta" id="chatSubHeader">Histórico em tempo real</div>
          </div>
          <div class="chat-body" id="chatBody">
            <div class="empty">Sem conversa selecionada.</div>
          </div>
        </section>
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
    const d = new Date(iso);
    if (isNaN(d)) return "";
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const mo = String(d.getMonth() + 1).padStart(2, "0");
    return `${{dd}}/${{mo}} ${{hh}}:${{mm}}`;
  }}

  async function loadLeads() {{
    const res = await fetch(`/admin/monitor/leads?key=${{encodeURIComponent(adminKey)}}`);
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
    const filtered = allLeads.filter(l =>
      String(l.name || "").toLowerCase().includes(q) ||
      String(l.phone_number || "").toLowerCase().includes(q)
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
    const shouldStickBottom = preserveScroll
      ? (body.scrollHeight - body.scrollTop - body.clientHeight) < 120
      : true;

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
    }}
  }}

  function refreshOpenChat() {{
    if (selectedPhone) {{
      openChat(selectedPhone, true);
    }}
  }}

  document.getElementById("search").addEventListener("input", renderLeads);
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
          <th>Enviado</th>
          <th>Responderam</th>
          <th>Taxa resp. ${{tip("% de leads que responderam após receber esta mensagem de follow-up")}}</th>
        </tr></thead>
        <tbody>
          ${{rows.map(r => `
            <tr>
              <td><strong>${{r.label}}</strong></td>
              <td>${{r.sent}}</td>
              <td>${{r.replied}}</td>
              <td>${{ratePill(r.reply_rate)}}</td>
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
</script>
</body>
</html>
"""
    return HTMLResponse(content=page)


@router.get("/monitor/leads")
async def admin_monitor_leads(
    x_admin_key: str | None = Header(default=None),
    key: str | None = Query(default=None),
):
    """Lista leads em atendimento com preview da última mensagem (dados do Redis)."""
    _authorize_admin(x_admin_key, key)

    leads_payload: list[dict] = []

    async for lead in iter_leads():
        if lead.stage in {LeadStage.CONVERTED, LeadStage.LOST}:
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
        ref = lead.created_at if lead.created_at else lead.last_inbound_at
        if ref is None:
            return dt_from is None and dt_to is None
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
            if sent > 0:
                fu_list.append({
                    "step": step_idx,
                    "label": timing,
                    "sent": sent,
                    "replied": replied,
                    "reply_rate": round(replied / sent * 100, 1) if sent else 0,
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
