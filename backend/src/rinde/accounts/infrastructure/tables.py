"""Tabla de cuentas (SQLAlchemy Core).

Las reglas del dominio se repiten como restricciones de la base: si algún día
alguien escribe una fila sin pasar por el dominio, la base la rechaza igual.
"""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Table, Uuid

from rinde.shared.infrastructure.database import metadata

accounts = Table(
    "accounts",
    metadata,
    Column("id", Uuid, primary_key=True),
    # El borrado de un usuario borra sus cuentas: es el borrado completo de sus datos.
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(60), nullable=False),
    Column("kind", String(16), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("archived_at", DateTime(timezone=True), nullable=True),
    CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 60", name="name_length"),
    CheckConstraint("kind IN ('cash', 'bank', 'credit_card', 'crypto_wallet')", name="kind_known"),
    CheckConstraint("currency IN ('ARS', 'USD', 'BTC')", name="currency_known"),
    CheckConstraint(
        "currency <> 'BTC' OR kind = 'crypto_wallet'", name="btc_only_in_crypto_wallet"
    ),
    CheckConstraint(
        "archived_at IS NULL OR archived_at >= created_at", name="archived_after_created"
    ),
    Index("ix_accounts_owner_id_created_at", "owner_id", "created_at"),
)
