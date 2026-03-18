import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services import whatsapp

logger = structlog.get_logger()
router = APIRouter()


class OutboundTemplateRequest(BaseModel):
    phone_number: str = Field(..., description="Número do lead com DDI (somente números ou formatado)")
    template_name: str = Field(..., description="Nome do template aprovado na Meta")
    language_code: str = Field(default="pt_BR", description="Idioma do template (ex: pt_BR)")
    body_params: list[str] = Field(default_factory=list, description="Parâmetros do body na ordem do template")


def _authorize_admin(x_admin_key: str | None) -> None:
    if not x_admin_key or x_admin_key != settings.app_secret:
        raise HTTPException(status_code=401, detail="Não autorizado")


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
