"""Crea los movimientos recurrentes (ADR-0027).

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recurring_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("frequency", sa.String(length=8), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "currency = 'BTC' OR amount = round(amount, 2)",
            name=op.f("ck_recurring_rules_amount_fits_the_currency"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_recurring_rules_amount_positive")),
        sa.CheckConstraint(
            "cancelled_at IS NULL OR cancelled_at >= created_at",
            name=op.f("ck_recurring_rules_cancelled_after_created"),
        ),
        sa.CheckConstraint(
            "frequency IN ('weekly', 'monthly', 'yearly')",
            name=op.f("ck_recurring_rules_frequency_known"),
        ),
        sa.CheckConstraint(
            "kind IN ('income', 'expense')", name=op.f("ck_recurring_rules_kind_known")
        ),
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
            name=op.f("fk_recurring_rules_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recurring_rules")),
    )
    op.create_index("ix_recurring_rules_category_id", "recurring_rules", ["category_id"])
    op.create_index(
        "ix_recurring_rules_owner_id_starts_on",
        "recurring_rules",
        ["owner_id", sa.literal_column("starts_on DESC")],
    )
    op.create_index(
        "uq_recurring_rules_id_owner_account",
        "recurring_rules",
        ["id", "owner_id", "account_id"],
        unique=True,
    )

    op.add_column("transactions", sa.Column("recurring_rule_id", sa.Uuid(), nullable=True))
    op.add_column("transactions", sa.Column("recurrence_number", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "occurrence_of_the_same_rule_owner_and_account",
        "transactions",
        "recurring_rules",
        ["recurring_rule_id", "owner_id", "account_id"],
        ["id", "owner_id", "account_id"],
    )
    op.create_check_constraint(
        op.f("ck_transactions_recurrence_complete"),
        "transactions",
        "(recurring_rule_id IS NULL) = (recurrence_number IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_transactions_recurrence_number_positive"),
        "transactions",
        "recurrence_number IS NULL OR recurrence_number >= 1",
    )
    op.create_check_constraint(
        op.f("ck_transactions_one_origin_at_most"),
        "transactions",
        "installment_plan_id IS NULL OR recurring_rule_id IS NULL",
    )
    op.create_index(
        "uq_transactions_recurring_rule_id_number",
        "transactions",
        ["recurring_rule_id", "recurrence_number"],
        unique=True,
        postgresql_where=sa.text("recurring_rule_id IS NOT NULL"),
    )

    # Una clave de idempotencia también puede haber creado una regla.
    op.drop_constraint(
        op.f("ck_idempotency_keys_resource_known"), "idempotency_keys", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_idempotency_keys_resource_known"),
        "idempotency_keys",
        "resource IN ('transaction', 'transfer', 'installment_plan', 'recurring_rule')",
    )


def downgrade() -> None:
    # Las claves de una regla no entran en la restricción vieja: se olvidan, como
    # cualquier clave vencida.
    op.execute("DELETE FROM idempotency_keys WHERE resource = 'recurring_rule'")
    op.drop_constraint(
        op.f("ck_idempotency_keys_resource_known"), "idempotency_keys", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_idempotency_keys_resource_known"),
        "idempotency_keys",
        "resource IN ('transaction', 'transfer', 'installment_plan')",
    )
    op.drop_index(
        "uq_transactions_recurring_rule_id_number",
        table_name="transactions",
        postgresql_where=sa.text("recurring_rule_id IS NOT NULL"),
    )
    op.drop_constraint(op.f("ck_transactions_one_origin_at_most"), "transactions", type_="check")
    op.drop_constraint(
        op.f("ck_transactions_recurrence_number_positive"), "transactions", type_="check"
    )
    op.drop_constraint(op.f("ck_transactions_recurrence_complete"), "transactions", type_="check")
    op.drop_constraint(
        "occurrence_of_the_same_rule_owner_and_account", "transactions", type_="foreignkey"
    )
    op.drop_column("transactions", "recurrence_number")
    op.drop_column("transactions", "recurring_rule_id")
    op.drop_table("recurring_rules")
