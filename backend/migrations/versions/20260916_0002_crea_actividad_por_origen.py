"""Crea la actividad por dirección de origen para los límites de la fase 1.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_activity",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("client", sa.String(length=45), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_client_activity")),
    )
    op.create_index(
        "ix_client_activity_action_client_occurred_at",
        "client_activity",
        ["action", "client", "occurred_at"],
        unique=False,
    )
    # La limpieza borra por fecha sin mirar la acción: necesita su propio índice.
    op.create_index(
        "ix_client_activity_occurred_at",
        "client_activity",
        ["occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_client_activity_occurred_at", table_name="client_activity")
    op.drop_index("ix_client_activity_action_client_occurred_at", table_name="client_activity")
    op.drop_table("client_activity")
