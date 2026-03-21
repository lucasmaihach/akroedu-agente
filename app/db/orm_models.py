from sqlalchemy import String, Integer, Boolean, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class LeadORM(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    course_slug: Mapped[str] = mapped_column(String(50), default="unknown")
    stage: Mapped[str] = mapped_column(String(30), default="new")
    sprinthub_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    script_step: Mapped[int] = mapped_column(Integer, default=0)
    is_escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    price_ask_count: Mapped[int] = mapped_column(Integer, default=0)
    last_received_msg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Follow-up automático
    followup_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    followup_status: Mapped[str] = mapped_column(String(20), default="idle")
    followup_scenario: Mapped[str | None] = mapped_column(String(10), nullable=True)
    followup_step: Mapped[int] = mapped_column(Integer, default=0)
    followup_next_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    followup_anchor_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    followup_started_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    followup_finished_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    followup_stopped_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Controle de janela/fluxo
    last_inbound_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    price_sent_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    last_unknown_prompt_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    # Ativação outbound via CRM/template
    awaiting_template_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    pending_welcome_template: Mapped[bool] = mapped_column(Boolean, default=False)
    welcome_template_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    welcome_next_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ConversationORM(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(10))        # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class AudioLogORM(Base):
    __tablename__ = "audio_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    course_slug: Mapped[str] = mapped_column(String(50))
    script_step: Mapped[int] = mapped_column(Integer)
    audio_filename: Mapped[str] = mapped_column(String(200))
    sent_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class ProcessedMessageORM(Base):
    __tablename__ = "processed_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    processed_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class PendingJobORM(Base):
    __tablename__ = "pending_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    run_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
