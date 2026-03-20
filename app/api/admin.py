import html
from datetime import datetime

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.memory.session import get_history, iter_leads
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
    body {{ margin: 0; font-family: Arial, sans-serif; background:#f4f6f8; color:#1f2937; }}
    .app {{ display:grid; grid-template-columns: 360px 1fr; height:100vh; }}
    .sidebar {{ border-right:1px solid #d1d5db; background:#fff; overflow:auto; }}
    .chat {{ display:flex; flex-direction:column; }}
    .header {{ padding:12px 16px; border-bottom:1px solid #d1d5db; background:#fff; }}
    .lead-item {{ padding:12px 14px; border-bottom:1px solid #eef2f7; cursor:pointer; }}
    .lead-item:hover {{ background:#f9fafb; }}
    .lead-item.active {{ background:#e8f0ff; }}
    .name {{ font-weight:700; }}
    .meta {{ font-size:12px; color:#6b7280; margin-top:4px; }}
    .preview {{ font-size:13px; margin-top:8px; color:#374151; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .chat-body {{ flex:1; overflow:auto; padding:16px; display:flex; flex-direction:column; gap:10px; }}
    .bubble {{ max-width:70%; padding:10px 12px; border-radius:12px; line-height:1.4; white-space:pre-wrap; }}
    .bubble.user {{ align-self:flex-start; background:#fff; border:1px solid #d1d5db; }}
    .bubble.assistant {{ align-self:flex-end; background:#dcfce7; border:1px solid #86efac; }}
    .bubble small {{ display:block; opacity:0.7; margin-top:6px; font-size:11px; }}
    .empty {{ padding:22px; color:#6b7280; }}
    .toolbar {{ padding:8px 12px; border-bottom:1px solid #e5e7eb; background:#fff; display:flex; gap:8px; align-items:center; }}
    input[type="text"] {{ width:100%; padding:8px; border:1px solid #d1d5db; border-radius:8px; }}
    .tag {{ background:#eef2ff; color:#4338ca; border-radius:999px; font-size:11px; padding:2px 8px; margin-left:6px; }}
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="toolbar">
        <input id="search" type="text" placeholder="Buscar por nome/telefone" />
      </div>
      <div id="leadList"></div>
    </aside>

    <section class="chat">
      <div class="header" id="chatHeader">Selecione um lead</div>
      <div class="chat-body" id="chatBody">
        <div class="empty">Sem conversa selecionada.</div>
      </div>
    </section>
  </div>

<script>
  const adminKey = "{safe_key}";
  let allLeads = [];
  let selectedPhone = null;

  function esc(text) {{
    return (text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
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
      (l.name || "").toLowerCase().includes(q) ||
      (l.phone_number || "").toLowerCase().includes(q)
    );

    const htmlLeads = filtered.map(l => `
      <div class="lead-item ${{selectedPhone===l.phone_number ? "active" : ""}}" onclick="openChat('${{l.phone_number}}')">
        <div class="name">${{esc(l.name || "Lead sem nome")}} <span class="tag">${{esc(l.stage)}}</span></div>
        <div class="meta">${{esc(l.phone_number)}} • ${{esc(l.course_slug)}} • passo ${{l.script_step}}</div>
        <div class="preview">${{esc(l.last_message_preview || "Sem mensagens")}}</div>
      </div>
    `).join("");

    document.getElementById("leadList").innerHTML = htmlLeads || "<div class='empty'>Nenhum lead encontrado.</div>";
  }}

  async function openChat(phone) {{
    selectedPhone = phone;
    renderLeads();

    const res = await fetch(`/admin/monitor/history/${{encodeURIComponent(phone)}}?key=${{encodeURIComponent(adminKey)}}`);
    if (!res.ok) {{
      document.getElementById("chatBody").innerHTML = `<div class='empty'>Erro ao carregar conversa (${{res.status}})</div>`;
      return;
    }}

    const data = await res.json();
    const lead = data.lead || {{}};
    const messages = data.messages || [];

    document.getElementById("chatHeader").innerText = `${{lead.name || "Lead sem nome"}} • ${{lead.phone_number || ""}} • ${{lead.stage || ""}}`;

    if (!messages.length) {{
      document.getElementById("chatBody").innerHTML = "<div class='empty'>Sem histórico para este lead.</div>";
      return;
    }}

    document.getElementById("chatBody").innerHTML = messages.map(m => `
      <div class="bubble ${{m.role === 'assistant' ? 'assistant' : 'user'}}">
        ${{esc(m.content)}}
        <small>${{m.role === 'assistant' ? 'Agente' : 'Lead'}}</small>
      </div>
    `).join("");

    const body = document.getElementById("chatBody");
    body.scrollTop = body.scrollHeight;
  }}

  document.getElementById("search").addEventListener("input", renderLeads);
  loadLeads();
  setInterval(loadLeads, 10000);
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
        last_msg = history[-1]["content"] if history else ""

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
            item.get("phone_number", ""),
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

    history = await get_history(clean_phone, last_n=200)
    return {
        "lead": {
            "phone_number": lead_found.phone_number,
            "name": lead_found.name,
            "stage": lead_found.stage.value,
            "course_slug": lead_found.course_slug.value,
            "script_step": lead_found.script_step,
        },
        "messages": history,
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
