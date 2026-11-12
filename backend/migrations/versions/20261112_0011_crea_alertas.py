"""Crea las alertas de presupuesto (ADR-0022).

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "budget_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=8), server_default=sa.text("'expense'"), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("threshold", sa.String(length=8), nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("spent_amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("raised_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "currency IN ('ARS', 'USD')", name=op.f("ck_budget_alerts_currency_allowed")
        ),
        sa.CheckConstraint("kind = 'expense'", name=op.f("ck_budget_alerts_kind_is_expense")),
        sa.CheckConstraint(
            "threshold IN ('warning', 'over')", name=op.f("ck_budget_alerts_threshold_allowed")
        ),
        sa.CheckConstraint(
            "extract(day FROM month) = 1", name=op.f("ck_budget_alerts_month_first_day")
        ),
        sa.CheckConstraint("limit_amount > 0", name=op.f("ck_budget_alerts_limit_positive")),
        sa.CheckConstraint(
            "read_at IS NULL OR read_at >= raised_at",
            name=op.f("ck_budget_alerts_read_after_raised"),
        ),
        sa.CheckConstraint("spent_amount > 0", name=op.f("ck_budget_alerts_spent_positive")),
        sa.ForeignKeyConstraint(
            ["category_id", "owner_id", "kind"],
            ["categories.id", "categories.owner_id", "categories.kind"],
            name=op.f("fk_budget_alerts_category_of_the_same_owner_and_kind"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_budget_alerts_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_alerts")),
        sa.UniqueConstraint(
            "owner_id",
            "category_id",
            "month",
            "threshold",
            name="uq_budget_alerts_once_per_month_and_threshold",
        ),
    )
    op.create_index(
        "ix_budget_alerts_owner_id_raised_at", "budget_alerts", ["owner_id", "raised_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_budget_alerts_owner_id_raised_at", table_name="budget_alerts")
    op.drop_table("budget_alerts")
