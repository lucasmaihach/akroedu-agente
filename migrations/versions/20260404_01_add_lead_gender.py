"""add gender field to leads

Revision ID: 20260404_01
Revises: 20260330_01
Create Date: 2026-04-04 00:00:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260404_01"
down_revision = "20260330_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alguns bancos antigos não tinham a coluna `gender`, mas o ORM espera.
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS gender VARCHAR(10) NOT NULL DEFAULT 'male'")
    op.execute("UPDATE leads SET gender = 'male' WHERE gender IS NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE leads DROP COLUMN IF EXISTS gender")

