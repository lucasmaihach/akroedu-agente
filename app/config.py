from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Aplicação ───────────────────────────────────────────
    app_env: str = "development"
    app_secret: str = "dev-secret"
    log_level: str = "INFO"
    app_public_url: str = ""  # Ex: https://xxxx.ngrok-free.app

    # ── WhatsApp Meta API ───────────────────────────────────
    meta_verify_token: str
    meta_access_token: str
    meta_phone_number_id: str
    meta_api_version: str = "v20.0"

    # ── Anthropic / Claude ──────────────────────────────────
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-5"

    # ── Groq (transcrição de áudio via Whisper) ─────────────
    groq_api_key: str = ""  # opcional — deixe vazio para desativar transcrição

    # ── Redis ───────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_hours: int = 48

    # ── PostgreSQL ──────────────────────────────────────────
    database_url: str
    postgres_user: str = "sales_agent"
    postgres_password: str = "password"
    postgres_db: str = "sales_agent_db"

    # ── SprintHub ───────────────────────────────────────────
    sprinthub_api_url: str = "https://api.sprinthub.com.br"
    sprinthub_api_key: str
    sprinthub_pipeline_curso_1: str = ""
    sprinthub_pipeline_curso_2: str = ""
    sprinthub_pipeline_pos_fisio_neuro: str = ""

    # ── Escalação ───────────────────────────────────────────
    escalation_whatsapp_number: str
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── Cursos ──────────────────────────────────────────────
    course_slugs: str = "curso_1,curso_2,pos_fisio_neuro"

    @property
    def course_slugs_list(self) -> List[str]:
        return [s.strip() for s in self.course_slugs.split(",")]

    @property
    def meta_api_url(self) -> str:
        return f"https://graph.facebook.com/{self.meta_api_version}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
