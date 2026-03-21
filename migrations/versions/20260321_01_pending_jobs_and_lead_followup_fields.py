"""add pending jobs and full lead runtime persistence

Revision ID: 20260321_01
Revises: 
Create Date: 2026-03-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260321_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # leads: persistência completa para continuidade e follow-up
    op.add_column("leads", sa.Column("followup_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("leads", sa.Column("followup_status", sa.String(length=20), nullable=False, server_default="idle"))
    op.add_column("leads", sa.Column("followup_scenario", sa.String(length=10), nullable=True))
    op.add_column("leads", sa.Column("followup_step", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("leads", sa.Column("followup_next_at", sa.DateTime(), nullable=True))
    op.add_column("leads", sa.Column("followup_anchor_at", sa.DateTime(), nullable=True))
    op.add_column("leads", sa.Column("followup_started_at", sa.DateTime(), nullable=True))
    op.add_column("leads", sa.Column("followup_finished_at", sa.DateTime(), nullable=True))
    op.add_column("leads", sa.Column("followup_stopped_reason", sa.String(length=100), nullable=True))

    op.add_column("leads", sa.Column("last_inbound_at", sa.DateTime(), nullable=True))
    op.add_column("leads", sa.Column("price_sent_at", sa.DateTime(), nullable=True))
    op.add_column("leads", sa.Column("last_unknown_prompt_at", sa.DateTime(), nullable=True))

    op.add_column("leads", sa.Column("awaiting_template_reply", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("leads", sa.Column("pending_welcome_template", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("leads", sa.Column("welcome_template_name", sa.String(length=100), nullable=True))
    op.add_column("leads", sa.Column("welcome_next_at", sa.DateTime(), nullable=True))

    # remove server defaults para manter comportamento no app
    op.alter_column("leads", "followup_enabled", server_default=None)
    op.alter_column("leads", "followup_status", server_default=None)
    op.alter_column("leads", "followup_step", server_default=None)
    op.alter_column("leads", "awaiting_template_reply", server_default=None)
    op.alter_column("leads", "pending_welcome_template", server_default=None)

    # fila de jobs persistentes (debounce inbound / FAQ delayed resume)
    op.create_table(
        "pending_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("phone_number", sa.String(length=20), nullable=False),
        sa.Column("run_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_pending_jobs_job_type", "pending_jobs", ["job_type"])
    op.create_index("ix_pending_jobs_phone_number", "pending_jobs", ["phone_number"])
    op.create_index("ix_pending_jobs_run_at", "pending_jobs", ["run_at"])
    op.create_index("ix_pending_jobs_status", "pending_jobs", ["status"])

    op.alter_column("pending_jobs", "status", server_default=None)
    op.alter_column("pending_jobs", "attempts", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_pending_jobs_status", table_name="pending_jobs")
    op.drop_index("ix_pending_jobs_run_at", table_name="pending_jobs")
    op.drop_index("ix_pending_jobs_phone_number", table_name="pending_jobs")
    op.drop_index("ix_pending_jobs_job_type", table_name="pending_jobs")
    op.drop_table("pending_jobs")

    op.drop_column("leads", "welcome_next_at")
    op.drop_column("leads", "welcome_template_name")
    op.drop_column("leads", "pending_welcome_template")
    op.drop_column("leads", "awaiting_template_reply")

    op.drop_column("leads", "last_unknown_prompt_at")
    op.drop_column("leads", "price_sent_at")
    op.drop_column("leads", "last_inbound_at")

    op.drop_column("leads", "followup_stopped_reason")
    op.drop_column("leads", "followup_finished_at")
    op.drop_column("leads", "followup_started_at")
    op.drop_column("leads", "followup_anchor_at")
    op.drop_column("leads", "followup_next_at")
    op.drop_column("leads", "followup_step")
    op.drop_column("leads", "followup_scenario")
    op.drop_column("leads", "followup_status")
    op.drop_column("leads", "followup_enabled")
