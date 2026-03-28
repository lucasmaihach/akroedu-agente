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
    .app {{ display:grid; grid-template-columns: 320px 1fr; height:100vh; overflow:hidden; }}
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
  </style>
</head>
<body>
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
