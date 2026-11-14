"""Crea el IPC guardado para los pesos constantes (ADR-0025).

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cpi_months",
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM month) = 1", name=op.f("ck_cpi_months_first_day_of_month")
        ),
        sa.CheckConstraint("value > 0", name=op.f("ck_cpi_months_positive")),
        sa.CheckConstraint("source IN ('indec')", name=op.f("ck_cpi_months_source_known")),
        sa.PrimaryKeyConstraint("month", name=op.f("pk_cpi_months")),
    )


def downgrade() -> None:
    op.drop_table("cpi_months")
