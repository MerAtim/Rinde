"""Crea los lotes de importación y sus líneas (ADR-0023).

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "file_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_import_batches_file_sha256_is_sha256")
        ),
        sa.CheckConstraint(
            "char_length(btrim(file_name)) BETWEEN 1 AND 255",
            name=op.f("ck_import_batches_file_name_length"),
        ),
        sa.CheckConstraint(
            "confirmed_at IS NOT NULL OR (imported = 0 AND skipped = 0)",
            name=op.f("ck_import_batches_counts_only_when_confirmed"),
        ),
        sa.CheckConstraint(
            "confirmed_at IS NULL OR confirmed_at >= created_at",
            name=op.f("ck_import_batches_confirmed_after_created"),
        ),
        sa.CheckConstraint(
            "imported >= 0 AND skipped >= 0", name=op.f("ck_import_batches_counts_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "owner_id", "currency"],
            ["accounts.id", "accounts.owner_id", "accounts.currency"],
            name=op.f("fk_import_batches_account_of_the_same_owner_and_currency"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_import_batches_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batches")),
    )
    op.create_index(
        "ix_import_batches_created_at_pending",
        "import_batches",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("confirmed_at IS NULL"),
    )
    op.create_table(
        "import_lines",
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=120), nullable=True),
        sa.Column("amount", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            "fingerprint ~ '^[0-9a-f]{64}$'", name=op.f("ck_import_lines_fingerprint_is_sha256")
        ),
        sa.CheckConstraint(
            "status IN ('new', 'duplicate', 'possible_duplicate')",
            name=op.f("ck_import_lines_status_known"),
        ),
        sa.CheckConstraint("amount <> 0", name=op.f("ck_import_lines_amount_not_zero")),
        sa.CheckConstraint("number >= 1", name=op.f("ck_import_lines_number_positive")),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["import_batches.id"],
            name=op.f("fk_import_lines_batch_id_import_batches"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("batch_id", "number", name=op.f("pk_import_lines")),
    )


def downgrade() -> None:
    op.drop_table("import_lines")
    op.drop_index(
        "ix_import_batches_created_at_pending",
        table_name="import_batches",
        postgresql_where=sa.text("confirmed_at IS NULL"),
    )
    op.drop_table("import_batches")
