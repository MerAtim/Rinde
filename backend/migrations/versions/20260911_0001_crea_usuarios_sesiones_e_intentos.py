"""Crea usuarios, sesiones e intentos fallidos de inicio de sesión (ADR-0007).

Revision ID: 0001
Revises:
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=30), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("recovery_code_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("username = lower(username)", name=op.f("ck_users_username_lowercase")),
        sa.CheckConstraint(
            "char_length(username) BETWEEN 3 AND 30", name=op.f("ck_users_username_length")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_sessions_expires_after_created")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_sessions")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_table(
        "failed_login_attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("username", sa.String(length=30), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_failed_login_attempts")),
    )
    op.create_index(
        "ix_failed_login_attempts_username_attempted_at",
        "failed_login_attempts",
        ["username", "attempted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_failed_login_attempts_username_attempted_at", table_name="failed_login_attempts"
    )
    op.drop_table("failed_login_attempts")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
