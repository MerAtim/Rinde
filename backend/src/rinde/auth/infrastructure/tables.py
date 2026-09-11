"""Tablas de autenticación (SQLAlchemy Core).

El dominio no las conoce: los repositorios traducen entre filas y entidades.
"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Table,
    Uuid,
)

from rinde.shared.infrastructure.database import metadata

users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("username", String(30), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("recovery_code_hash", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("username = lower(username)", name="username_lowercase"),
    CheckConstraint("char_length(username) BETWEEN 3 AND 30", name="username_length"),
)

sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column(
        "user_id",
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("expires_at > created_at", name="expires_after_created"),
)

failed_login_attempts = Table(
    "failed_login_attempts",
    metadata,
    Column("id", BigInteger, Identity(always=True), primary_key=True),
    Column("username", String(30), nullable=False),
    Column("attempted_at", DateTime(timezone=True), nullable=False),
    Index("ix_failed_login_attempts_username_attempted_at", "username", "attempted_at"),
)
