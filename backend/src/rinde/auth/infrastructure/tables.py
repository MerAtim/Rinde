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
    text,
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
    # Solo en una demo (ADR-0028); en una cuenta común es NULL.
    Column("demo_expires_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("username = lower(username)", name="username_lowercase"),
    CheckConstraint("char_length(username) BETWEEN 3 AND 30", name="username_length"),
    CheckConstraint(
        "demo_expires_at IS NULL OR demo_expires_at > created_at",
        name="demo_expires_after_created",
    ),
    # El nombre y la vigencia van juntos: una demo se llama demo-algo, y nadie más.
    CheckConstraint(
        "(demo_expires_at IS NOT NULL) = (username LIKE 'demo-%')",
        name="demo_name_matches",
    ),
    Index(
        "ix_users_demo_expires_at",
        "demo_expires_at",
        postgresql_where=text("demo_expires_at IS NOT NULL"),
    ),
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

# Actividad por dirección de origen. Se guarda la dirección en claro porque es
# lo único que permite contarla, y se borra sola pasada la ventana más larga
# (una hora): es el dato mínimo, por el tiempo mínimo.
client_activity = Table(
    "client_activity",
    metadata,
    Column("id", BigInteger, Identity(always=True), primary_key=True),
    Column("action", String(32), nullable=False),
    # 45 caracteres: lo que ocupa una IPv6 escrita con una IPv4 adentro.
    Column("client", String(45), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Index("ix_client_activity_action_client_occurred_at", "action", "client", "occurred_at"),
    Index("ix_client_activity_occurred_at", "occurred_at"),
)

failed_login_attempts = Table(
    "failed_login_attempts",
    metadata,
    Column("id", BigInteger, Identity(always=True), primary_key=True),
    Column("username", String(30), nullable=False),
    Column("attempted_at", DateTime(timezone=True), nullable=False),
    Index("ix_failed_login_attempts_username_attempted_at", "username", "attempted_at"),
)

# Constancia de cada baja: solo el identificador y la fecha, ningún dato de la
# persona. Sin clave foránea a propósito: la cuenta ya no existe. Si se restaura
# un respaldo anterior a la baja, esta lista dice qué cuentas volver a borrar
# (ADR-0034).
account_deletions = Table(
    "account_deletions",
    metadata,
    Column("user_id", Uuid, primary_key=True),
    Column("deleted_at", DateTime(timezone=True), nullable=False),
)
