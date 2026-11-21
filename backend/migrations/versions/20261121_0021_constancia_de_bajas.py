"""Constancia de las cuentas borradas por sus dueños (ADR-0034).

Guarda solo el identificador y la fecha de cada baja, sin clave foránea: la
cuenta ya no existe. Si se restaura un respaldo anterior, dice qué cuentas
volver a borrar.

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_deletions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_account_deletions")),
    )


def downgrade() -> None:
    op.drop_table("account_deletions")
