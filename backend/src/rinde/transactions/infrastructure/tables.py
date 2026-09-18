"""Tablas de movimientos, categorías, auditoría e idempotencia (SQLAlchemy Core).

Las reglas del dominio se repiten como restricciones de la base: si algún día
alguien escribe una fila sin pasar por el dominio, la base la rechaza igual.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Table,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from rinde.shared.infrastructure.database import metadata

_KINDS = "('income', 'expense')"

categories = Table(
    "categories",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(40), nullable=False),
    Column("kind", String(8), nullable=False),
    # Solo en las sembradas: la interfaz las traduce por este identificador (ADR-0011).
    Column("slug", String(40), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 40", name="name_length"),
    CheckConstraint(f"kind IN {_KINDS}", name="kind_known"),
    # El movimiento apunta a (id, dueño, tipo): así la base garantiza que una
    # categoría de gastos no clasifique un ingreso, y que sea de la misma persona.
    Index("uq_categories_id_owner_id_kind", "id", "owner_id", "kind", unique=True),
    # "Súper" y "súper" son la misma categoría dentro de un tipo.
    Index(
        "uq_categories_owner_id_kind_name",
        "owner_id",
        "kind",
        func.lower(text("name")),
        unique=True,
    ),
    # Una sola categoría sembrada por identificador: la siembra repetida no duplica.
    Index(
        "uq_categories_owner_id_slug",
        "owner_id",
        "slug",
        unique=True,
        postgresql_where=text("slug IS NOT NULL"),
    ),
)

transactions = Table(
    "transactions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("account_id", Uuid, nullable=False),
    # La moneda se guarda al lado del monto y la clave foránea la ata a la de la
    # cuenta: un gasto en dólares no puede entrar en una caja en pesos (ADR-0011).
    Column("currency", String(3), nullable=False),
    Column("kind", String(8), nullable=False),
    Column("amount", Numeric(20, 8), nullable=False),
    Column("category_id", Uuid, nullable=False),
    Column("occurred_on", Date, nullable=False),
    Column("description", String(120), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    ForeignKeyConstraint(
        ["account_id", "owner_id", "currency"],
        ["accounts.id", "accounts.owner_id", "accounts.currency"],
        name="account_of_the_same_owner_and_currency",
    ),
    ForeignKeyConstraint(
        ["category_id", "owner_id", "kind"],
        ["categories.id", "categories.owner_id", "categories.kind"],
        name="category_of_the_same_owner_and_kind",
    ),
    CheckConstraint("amount > 0", name="amount_positive"),
    # Cada moneda tiene su precisión: 2 decimales, salvo Bitcoin, que admite 8.
    CheckConstraint(
        "currency = 'BTC' OR amount = round(amount, 2)", name="amount_fits_the_currency"
    ),
    CheckConstraint(f"kind IN {_KINDS}", name="kind_known"),
    CheckConstraint("deleted_at IS NULL OR deleted_at >= created_at", name="deleted_after_created"),
    CheckConstraint("updated_at >= created_at", name="updated_after_created"),
    # Índices parciales: las lecturas solo miran los movimientos vivos (ADR-0011).
    Index(
        "ix_transactions_owner_id_occurred_on",
        "owner_id",
        text("occurred_on DESC"),
        text("id DESC"),
        postgresql_where=text("deleted_at IS NULL"),
    ),
    Index(
        "ix_transactions_owner_id_account_id_occurred_on",
        "owner_id",
        "account_id",
        text("occurred_on DESC"),
        text("id DESC"),
        postgresql_where=text("deleted_at IS NULL"),
    ),
    Index(
        "ix_transactions_category_id",
        "category_id",
        postgresql_where=text("deleted_at IS NULL"),
    ),
)

# Append-only: un disparador rechaza actualizar y borrar (ADR-0011).
transaction_audit = Table(
    "transaction_audit",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("transaction_id", Uuid, nullable=False),
    Column("owner_id", Uuid, nullable=False),
    Column("action", String(16), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    # Cómo quedó el movimiento después de la acción, para poder reconstruir la historia.
    Column("snapshot", JSONB, nullable=False),
    CheckConstraint(
        "action IN ('registered', 'edited', 'deleted', 'restored')", name="action_known"
    ),
    Index("ix_transaction_audit_transaction_id_recorded_at", "transaction_id", "recorded_at"),
)

idempotency_keys = Table(
    "idempotency_keys",
    metadata,
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("key", String(255), primary_key=True),
    Column("fingerprint", String(64), nullable=False),
    Column("transaction_id", Uuid, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_idempotency_keys_created_at", "created_at"),
)
