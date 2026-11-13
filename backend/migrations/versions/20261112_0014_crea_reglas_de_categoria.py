"""Crea las reglas de categoría al importar (ADR-0024).

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "category_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("pattern", sa.String(length=60), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('income', 'expense')", name=op.f("ck_category_rules_kind_known")
        ),
        sa.CheckConstraint(
            "char_length(pattern) BETWEEN 3 AND 60", name=op.f("ck_category_rules_pattern_length")
        ),
        sa.CheckConstraint(
            "pattern = lower(pattern)", name=op.f("ck_category_rules_pattern_folded")
        ),
        sa.ForeignKeyConstraint(
            ["category_id", "owner_id", "kind"],
            ["categories.id", "categories.owner_id", "categories.kind"],
            name=op.f("fk_category_rules_category_of_the_same_owner_and_kind"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_category_rules_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category_rules")),
        sa.UniqueConstraint(
            "owner_id", "kind", "pattern", name="uq_category_rules_owner_kind_pattern"
        ),
    )


def downgrade() -> None:
    op.drop_table("category_rules")
