"""Crea el histórico de cotizaciones (ADR-0002, ADR-0016).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("base", sa.String(length=3), nullable=False),
        sa.Column("counter", sa.String(length=3), nullable=False),
        sa.Column("rate_type", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("buy", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("sell", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("buy > 0 AND sell > 0", name=op.f("ck_exchange_rates_positive")),
        sa.CheckConstraint("buy <= sell", name=op.f("ck_exchange_rates_buy_not_above_sell")),
        sa.CheckConstraint("base <> counter", name=op.f("ck_exchange_rates_different_currencies")),
        sa.CheckConstraint(
            "base IN ('ARS', 'USD', 'BTC')", name=op.f("ck_exchange_rates_base_known")
        ),
        sa.CheckConstraint(
            "counter IN ('ARS', 'USD', 'BTC')", name=op.f("ck_exchange_rates_counter_known")
        ),
        sa.CheckConstraint(
            "rate_type IN ('official', 'mep', 'ccl', 'blue', 'card', 'crypto')",
            name=op.f("ck_exchange_rates_rate_type_known"),
        ),
        sa.CheckConstraint(
            "source IN ('dolarapi', 'argentinadatos', 'criptoya')",
            name=op.f("ck_exchange_rates_source_known"),
        ),
        sa.PrimaryKeyConstraint(
            "day", "base", "counter", "rate_type", "source", name=op.f("pk_exchange_rates")
        ),
    )


def downgrade() -> None:
    op.drop_table("exchange_rates")
