"""Agrega la huella de importación a los movimientos (ADR-0023).

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nula en todos los movimientos que ya existen: ninguno vino de un archivo.
    op.add_column(
        "transactions", sa.Column("source_fingerprint", sa.String(length=64), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_transactions_source_fingerprint_is_sha256"),
        "transactions",
        "source_fingerprint IS NULL OR source_fingerprint ~ '^[0-9a-f]{64}$'",
    )
    op.create_index(
        "uq_transactions_account_id_source_fingerprint",
        "transactions",
        ["account_id", "source_fingerprint"],
        unique=True,
        postgresql_where=sa.text("source_fingerprint IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_transactions_account_id_source_fingerprint",
        table_name="transactions",
        postgresql_where=sa.text("source_fingerprint IS NOT NULL"),
    )
    op.drop_constraint(
        op.f("ck_transactions_source_fingerprint_is_sha256"), "transactions", type_="check"
    )
    op.drop_column("transactions", "source_fingerprint")
