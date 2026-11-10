"""Crea las preferencias de cada persona (ADR-0017).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("reference_currency", sa.String(length=3), nullable=False),
        sa.Column("rate_type", sa.String(length=16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "reference_currency IN ('ARS', 'USD')",
            name=op.f("ck_user_preferences_reference_currency_known"),
        ),
        sa.CheckConstraint(
            "rate_type IN ('official', 'mep', 'ccl', 'blue', 'card', 'crypto')",
            name=op.f("ck_user_preferences_rate_type_known"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_user_preferences_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("owner_id", name=op.f("pk_user_preferences")),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
