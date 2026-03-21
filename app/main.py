import sys
import time
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

if sys.version_info < (3, 11):
    raise RuntimeError("Python 3.11+ é obrigatório para executar o Sales Agent.")

from app.config import settings
from app.api.webhooks import router as webhook_router
from app.api.crm_webhooks import router as crm_webhook_router
from app.api.admin import router as admin_router
from app.memory.session import init_redis
from app.db.database import init_db
from app.followup import FollowupWorker
from app.services.error_alert import notify_api_error

logger = structlog.get_logger()
followup_worker = FollowupWorker(poll_seconds=5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa conexões na subida e encerra na descida."""
    logger.info("🚀 Sales Agent iniciando...", env=settings.app_env)
    await init_redis()
    await init_db()
    await followup_worker.start()
    logger.info("✅ Conexões estabelecidas com sucesso.")
    yield
    await followup_worker.stop()
    logger.info("🛑 Sales Agent encerrando...")


app = FastAPI(
    title="Sales Agent — Pós-Graduação",
    description="Agente de vendas via WhatsApp para cursos de pós-graduação",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(webhook_router, prefix="/webhook", tags=["WhatsApp Webhook"])
app.include_router(crm_webhook_router, prefix="/webhook", tags=["CRM Webhook"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])
app.mount("/audios", StaticFiles(directory="/app/audios"), name="audios")


@app.middleware("http")
async def api_error_alert_middleware(request: Request, call_next):
    started_at = time.perf_counter()

    # Lê o body uma vez e rehidrata para os handlers/rotas.
    body = await request.body()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        await notify_api_error(
            request,
            status_code=500,
            error=exc,
            duration_ms=duration_ms,
            request_body=body,
        )
        raise

    if response.status_code >= 500:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        await notify_api_error(
            request,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_body=body,
        )

    return response


@app.get("/health")
async def health_check():
    return {"status": "ok", "env": settings.app_env}
