"""add agent_paused and last_script_block fields for agent pause/resume control

Revision ID: 20260330_01
Revises: 20260321_02
Create Date: 2026-03-30 09:15:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260330_01"
down_revision = "20260321_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add fields for pause/resume agent control and script tracking"""
    # Add agent_paused flag
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS agent_paused BOOLEAN NOT NULL DEFAULT FALSE")

    # Add script tracking
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_script_block VARCHAR(255)")

    # Create index for pause/resume queries
    op.execute("CREATE INDEX IF NOT EXISTS idx_leads_agent_paused ON leads (agent_paused)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_leads_last_script_block ON leads (last_script_block)")


def downgrade() -> None:
    """Remove agent control fields"""
    op.execute("DROP INDEX IF EXISTS idx_leads_last_script_block")
    op.execute("DROP INDEX IF EXISTS idx_leads_agent_paused")
    op.execute("ALTER TABLE leads DROP COLUMN IF EXISTS last_script_block")
    op.execute("ALTER TABLE leads DROP COLUMN IF EXISTS agent_paused")
