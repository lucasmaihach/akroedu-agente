import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.webhooks import router as webhook_router
from app.api.crm_webhooks import router as crm_webhook_router
from app.api.admin import router as admin_router
from app.memory.session import init_redis
from app.db.database import init_db
from app.followup import FollowupWorker

logger = structlog.get_logger()
followup_worker = FollowupWorker(poll_seconds=30)


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


@app.get("/health")
async def health_check():
    return {"status": "ok", "env": settings.app_env}
