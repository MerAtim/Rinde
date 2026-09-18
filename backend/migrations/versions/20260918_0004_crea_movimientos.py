"""Crea los movimientos, las categorías, la auditoría y las claves de idempotencia (ADR-0011).

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# El log de auditoría solo admite inserciones (ADR-0011). La regla vive en la
# base y no en el código: así vale también para quien entre por psql.
_AUDIT_GUARD = """
CREATE OR REPLACE FUNCTION transaction_audit_is_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'transaction_audit es append-only: no se puede % una fila', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER transaction_audit_no_update_or_delete
BEFORE UPDATE OR DELETE ON transaction_audit
FOR EACH ROW EXECUTE FUNCTION transaction_audit_is_append_only();
"""


def upgrade() -> None:
    op.create_unique_constraint(
        op.f("uq_accounts_id_owner_id_currency"), "accounts", ["id", "owner_id", "currency"]
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(btrim(name)) BETWEEN 1 AND 40", name=op.f("ck_categories_name_length")
        ),
        sa.CheckConstraint("kind IN ('income', 'expense')", name=op.f("ck_categories_kind_known")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_categories_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
    )
    op.create_index(
        "uq_categories_id_owner_id_kind", "categories", ["id", "owner_id", "kind"], unique=True
    )
    op.create_index(
        "uq_categories_owner_id_kind_name",
        "categories",
        ["owner_id", "kind", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index(
        "uq_categories_owner_id_slug",
        "categories",
        ["owner_id", "slug"],
        unique=True,
        postgresql_where=sa.text("slug IS NOT NULL"),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name=op.f("ck_transactions_amount_positive")),
        sa.CheckConstraint(
            "currency = 'BTC' OR amount = round(amount, 2)",
            name=op.f("ck_transactions_amount_fits_the_currency"),
        ),
        sa.CheckConstraint(
            "kind IN ('income', 'expense')", name=op.f("ck_transactions_kind_known")
        ),
        sa.CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name=op.f("ck_transactions_deleted_after_created"),
        ),
        sa.CheckConstraint(
            "updated_at >= created_at", name=op.f("ck_transactions_updated_after_created")
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "owner_id", "currency"],
            ["accounts.id", "accounts.owner_id", "accounts.currency"],
            name=op.f("fk_transactions_account_of_the_same_owner_and_currency"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id", "owner_id", "kind"],
            ["categories.id", "categories.owner_id", "categories.kind"],
            name=op.f("fk_transactions_category_of_the_same_owner_and_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_transactions_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
    )
    op.create_index(
        "ix_transactions_owner_id_occurred_on",
        "transactions",
        ["owner_id", sa.text("occurred_on DESC"), sa.text("id DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_transactions_owner_id_account_id_occurred_on",
        "transactions",
        ["owner_id", "account_id", sa.text("occurred_on DESC"), sa.text("id DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_transactions_category_id",
        "transactions",
        ["category_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "transaction_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "action IN ('registered', 'edited', 'deleted', 'restored')",
            name=op.f("ck_transaction_audit_action_known"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transaction_audit")),
    )
    op.create_index(
        "ix_transaction_audit_transaction_id_recorded_at",
        "transaction_audit",
        ["transaction_id", "recorded_at"],
    )
    op.execute(_AUDIT_GUARD)

    op.create_table(
        "idempotency_keys",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_idempotency_keys_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("owner_id", "key", name=op.f("pk_idempotency_keys")),
    )
    op.create_index("ix_idempotency_keys_created_at", "idempotency_keys", ["created_at"])


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.execute("DROP TRIGGER IF EXISTS transaction_audit_no_update_or_delete ON transaction_audit")
    op.execute("DROP FUNCTION IF EXISTS transaction_audit_is_append_only()")
    op.drop_table("transaction_audit")
    op.drop_table("transactions")
    op.drop_table("categories")
    op.drop_constraint(op.f("uq_accounts_id_owner_id_currency"), "accounts", type_="unique")
