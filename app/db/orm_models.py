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
