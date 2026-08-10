"""add ai_percentage to commits

Revision ID: a1b2c3d4e5f6
Revises: d854f1f381a3
Create Date: 2026-08-04 10:03:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "d854f1f381a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "commits",
        sa.Column(
            "ai_percentage",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("commits", "ai_percentage")