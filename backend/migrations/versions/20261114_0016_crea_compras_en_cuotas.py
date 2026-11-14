"""Crea las compras en cuotas (ADR-0026).

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "installment_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("total", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("count", sa.SmallInteger(), nullable=False),
        sa.Column("first_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "currency = 'BTC' OR total = round(total, 2)",
            name=op.f("ck_installment_plans_total_fits_the_currency"),
        ),
        sa.CheckConstraint("kind = 'expense'", name=op.f("ck_installment_plans_is_an_expense")),
        sa.CheckConstraint(
            "total >= count * CASE WHEN currency = 'BTC' THEN 0.00000001 ELSE 0.01 END",
            name=op.f("ck_installment_plans_every_installment_has_a_minimum"),
        ),
        sa.CheckConstraint(
            "cancelled_at IS NULL OR cancelled_at >= created_at",
            name=op.f("ck_installment_plans_cancelled_after_created"),
        ),
        sa.CheckConstraint(
            "count BETWEEN 2 AND 48", name=op.f("ck_installment_plans_count_in_range")
        ),
        sa.CheckConstraint("total > 0", name=op.f("ck_installment_plans_total_positive")),
        sa.ForeignKeyConstraint(
            ["account_id", "owner_id", "currency"],
            ["accounts.id", "accounts.owner_id", "accounts.currency"],
            name="account_of_the_same_owner_and_currency",
        ),
        sa.ForeignKeyConstraint(
            ["category_id", "owner_id", "kind"],
            ["categories.id", "categories.owner_id", "categories.kind"],
            name="category_of_the_same_owner_and_kind",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_installment_plans_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_installment_plans")),
    )
    op.create_index("ix_installment_plans_category_id", "installment_plans", ["category_id"])
    op.create_index(
        "ix_installment_plans_owner_id_first_on",
        "installment_plans",
        ["owner_id", sa.literal_column("first_on DESC")],
    )
    op.create_index(
        "uq_installment_plans_id_owner_account_count",
        "installment_plans",
        ["id", "owner_id", "account_id", "count"],
        unique=True,
    )

    op.add_column("transactions", sa.Column("installment_plan_id", sa.Uuid(), nullable=True))
    op.add_column("transactions", sa.Column("installment_number", sa.SmallInteger(), nullable=True))
    op.add_column("transactions", sa.Column("installment_count", sa.SmallInteger(), nullable=True))
    op.create_foreign_key(
        "installment_of_the_same_plan_owner_and_account",
        "transactions",
        "installment_plans",
        ["installment_plan_id", "owner_id", "account_id", "installment_count"],
        ["id", "owner_id", "account_id", "count"],
    )
    op.create_check_constraint(
        op.f("ck_transactions_installment_complete"),
        "transactions",
        "(installment_plan_id IS NULL) = (installment_number IS NULL)"
        " AND (installment_plan_id IS NULL) = (installment_count IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_transactions_installment_number_in_range"),
        "transactions",
        "installment_number IS NULL OR installment_number BETWEEN 1 AND installment_count",
    )
    op.create_check_constraint(
        op.f("ck_transactions_installment_is_an_expense"),
        "transactions",
        "installment_plan_id IS NULL OR kind = 'expense'",
    )
    op.create_index(
        "uq_transactions_installment_plan_id_number",
        "transactions",
        ["installment_plan_id", "installment_number"],
        unique=True,
        postgresql_where=sa.text("installment_plan_id IS NOT NULL"),
    )

    # Una clave de idempotencia también puede haber creado un plan.
    op.drop_constraint(
        op.f("ck_idempotency_keys_resource_known"), "idempotency_keys", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_idempotency_keys_resource_known"),
        "idempotency_keys",
        "resource IN ('transaction', 'transfer', 'installment_plan')",
    )


def downgrade() -> None:
    # Las claves de un plan no entran en la restricción vieja: se olvidan, como
    # cualquier clave vencida.
    op.execute("DELETE FROM idempotency_keys WHERE resource = 'installment_plan'")
    op.drop_constraint(
        op.f("ck_idempotency_keys_resource_known"), "idempotency_keys", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_idempotency_keys_resource_known"),
        "idempotency_keys",
        "resource IN ('transaction', 'transfer')",
    )
    op.drop_index(
        "uq_transactions_installment_plan_id_number",
        table_name="transactions",
        postgresql_where=sa.text("installment_plan_id IS NOT NULL"),
    )
    op.drop_constraint(
        op.f("ck_transactions_installment_is_an_expense"), "transactions", type_="check"
    )
    op.drop_constraint(
        op.f("ck_transactions_installment_number_in_range"), "transactions", type_="check"
    )
    op.drop_constraint(op.f("ck_transactions_installment_complete"), "transactions", type_="check")
    op.drop_constraint(
        "installment_of_the_same_plan_owner_and_account", "transactions", type_="foreignkey"
    )
    op.drop_column("transactions", "installment_count")
    op.drop_column("transactions", "installment_number")
    op.drop_column("transactions", "installment_plan_id")
    op.drop_table("installment_plans")
