"""reconcile leads and pending_jobs schema after partial/manual rollout

Revision ID: 20260321_02
Revises: 20260321_01
Create Date: 2026-03-21 18:45:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260321_02"
down_revision = "20260321_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # leads: garante colunas esperadas pelo ORM atual
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS price_ask_count INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_received_msg_id VARCHAR(100)")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS notes TEXT")

    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_enabled BOOLEAN NOT NULL DEFAULT TRUE")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_status VARCHAR(20) NOT NULL DEFAULT 'idle'")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_scenario VARCHAR(10)")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_step INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_next_at TIMESTAMP")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_anchor_at TIMESTAMP")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_started_at TIMESTAMP")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_finished_at TIMESTAMP")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_stopped_reason VARCHAR(100)")

    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_inbound_at TIMESTAMP")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS price_sent_at TIMESTAMP")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_unknown_prompt_at TIMESTAMP")

    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS awaiting_template_reply BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS pending_welcome_template BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS welcome_template_name VARCHAR(100)")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS welcome_next_at TIMESTAMP")

    # pending_jobs: garante tabela/índices mesmo em casos de criação parcial
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_jobs (
            id SERIAL PRIMARY KEY,
            job_type VARCHAR(50) NOT NULL,
            phone_number VARCHAR(20) NOT NULL,
            run_at TIMESTAMP NOT NULL,
            status VARCHAR(20) NOT NULL,
            payload TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        )
        """
    )

    op.execute("ALTER TABLE pending_jobs ADD COLUMN IF NOT EXISTS job_type VARCHAR(50)")
    op.execute("ALTER TABLE pending_jobs ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20)")
    op.execute("ALTER TABLE pending_jobs ADD COLUMN IF NOT EXISTS run_at TIMESTAMP")
    op.execute("ALTER TABLE pending_jobs ADD COLUMN IF NOT EXISTS status VARCHAR(20)")
    op.execute("ALTER TABLE pending_jobs ADD COLUMN IF NOT EXISTS payload TEXT")
    op.execute("ALTER TABLE pending_jobs ADD COLUMN IF NOT EXISTS attempts INTEGER")
    op.execute("ALTER TABLE pending_jobs ADD COLUMN IF NOT EXISTS last_error TEXT")
    op.execute("ALTER TABLE pending_jobs ADD COLUMN IF NOT EXISTS started_at TIMESTAMP")
    op.execute("ALTER TABLE pending_jobs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP")
    op.execute("ALTER TABLE pending_jobs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP")
    op.execute("ALTER TABLE pending_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP")

    op.execute("CREATE INDEX IF NOT EXISTS ix_pending_jobs_job_type ON pending_jobs (job_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pending_jobs_phone_number ON pending_jobs (phone_number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pending_jobs_run_at ON pending_jobs (run_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pending_jobs_status ON pending_jobs (status)")


def downgrade() -> None:
    # Migração de reconciliação: downgrade automático não é seguro neste caso.
    pass
