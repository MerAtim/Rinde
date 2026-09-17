"""Crea las cuentas (ADR-0009).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "char_length(btrim(name)) BETWEEN 1 AND 60", name=op.f("ck_accounts_name_length")
        ),
        sa.CheckConstraint(
            "kind IN ('cash', 'bank', 'credit_card', 'crypto_wallet')",
            name=op.f("ck_accounts_kind_known"),
        ),
        sa.CheckConstraint(
            "currency IN ('ARS', 'USD', 'BTC')", name=op.f("ck_accounts_currency_known")
        ),
        sa.CheckConstraint(
            "currency <> 'BTC' OR kind = 'crypto_wallet'",
            name=op.f("ck_accounts_btc_only_in_crypto_wallet"),
        ),
        sa.CheckConstraint(
            "archived_at IS NULL OR archived_at >= created_at",
            name=op.f("ck_accounts_archived_after_created"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_accounts_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
    )
    op.create_index(
        "ix_accounts_owner_id_created_at",
        "accounts",
        ["owner_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_accounts_owner_id_created_at", table_name="accounts")
    op.drop_table("accounts")
