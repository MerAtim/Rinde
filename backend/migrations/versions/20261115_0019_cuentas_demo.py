"""Cuentas demo que vencen solas (ADR-0028).

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("demo_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f("ck_users_demo_expires_after_created"),
        "users",
        "demo_expires_at IS NULL OR demo_expires_at > created_at",
    )
    # Si ya existiera una cuenta común llamada demo-algo, la migración falla a la
    # vista en vez de dejarla pasar por demo.
    op.create_check_constraint(
        op.f("ck_users_demo_name_matches"),
        "users",
        "(demo_expires_at IS NOT NULL) = (username LIKE 'demo-%')",
    )
    op.create_index(
        "ix_users_demo_expires_at",
        "users",
        ["demo_expires_at"],
        postgresql_where=sa.text("demo_expires_at IS NOT NULL"),
    )


def downgrade() -> None:
    # Las demos no sobreviven a la vuelta atrás: sin la columna serían cuentas
    # comunes sin dueño que pueda entrar.
    op.execute("DELETE FROM users WHERE demo_expires_at IS NOT NULL")
    op.drop_index("ix_users_demo_expires_at", table_name="users")
    op.drop_constraint(op.f("ck_users_demo_name_matches"), "users", type_="check")
    op.drop_constraint(op.f("ck_users_demo_expires_after_created"), "users", type_="check")
    op.drop_column("users", "demo_expires_at")
