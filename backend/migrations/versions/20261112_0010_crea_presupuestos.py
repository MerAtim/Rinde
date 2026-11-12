"""Crea las vigencias de los presupuestos (ADR-0021).

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "budget_limits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=8), server_default=sa.text("'expense'"), nullable=False),
        sa.Column("since", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "currency IN ('ARS', 'USD')", name=op.f("ck_budget_limits_currency_allowed")
        ),
        sa.CheckConstraint("kind = 'expense'", name=op.f("ck_budget_limits_kind_is_expense")),
        sa.CheckConstraint(
            "(amount IS NULL) = (currency IS NULL)",
            name=op.f("ck_budget_limits_amount_with_currency"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_budget_limits_amount_positive")),
        sa.CheckConstraint(
            "extract(day FROM since) = 1", name=op.f("ck_budget_limits_since_first_of_month")
        ),
        sa.ForeignKeyConstraint(
            ["category_id", "owner_id", "kind"],
            ["categories.id", "categories.owner_id", "categories.kind"],
            name=op.f("fk_budget_limits_category_of_the_same_owner_and_kind"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_budget_limits_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_limits")),
    )
    op.create_index(
        "uq_budget_limits_owner_id_category_id_since_recorded_at",
        "budget_limits",
        ["owner_id", "category_id", "since", "recorded_at"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_budget_limits_owner_id_category_id_since_recorded_at", table_name="budget_limits"
    )
    op.drop_table("budget_limits")
