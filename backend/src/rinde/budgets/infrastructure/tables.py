"""Tabla de vigencias de presupuestos (SQLAlchemy Core), solo de agregado (ADR-0021).

Las reglas del dominio se repiten como restricciones: si algún día alguien
escribe una fila sin pasar por el dominio, la base la rechaza igual.
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
    text,
)

from rinde.shared.infrastructure.database import metadata

budget_limits = Table(
    "budget_limits",
    metadata,
    Column("id", Uuid, primary_key=True),
    # El borrado de un usuario borra sus presupuestos: es el borrado completo de sus datos.
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("category_id", Uuid, nullable=False),
    # Siempre 'expense'. Va en la fila para que la clave foránea pida una
    # categoría de gastos de la misma persona, como hacen los movimientos.
    Column("kind", String(8), nullable=False, server_default=text("'expense'")),
    Column("since", Date, nullable=False),
    # Las dos en NULL: desde ese mes la categoría ya no tiene tope.
    Column("amount", Numeric(20, 2), nullable=True),
    Column("currency", String(3), nullable=True),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["category_id", "owner_id", "kind"],
        ["categories.id", "categories.owner_id", "categories.kind"],
        name="category_of_the_same_owner_and_kind",
        # Una categoría solo se borra si no tiene movimientos, y se lleva sus topes (ADR-0021).
        ondelete="CASCADE",
    ),
    CheckConstraint("kind = 'expense'", name="kind_is_expense"),
    CheckConstraint("extract(day FROM since) = 1", name="since_first_of_month"),
    CheckConstraint("(amount IS NULL) = (currency IS NULL)", name="amount_with_currency"),
    CheckConstraint("amount > 0", name="amount_positive"),
    CheckConstraint("currency IN ('ARS', 'USD')", name="currency_allowed"),
    # Las vigencias de una categoría están en un orden estricto: la última vale.
    # El índice también sirve para leer el historial de una persona.
    Index(
        "uq_budget_limits_owner_id_category_id_since_recorded_at",
        "owner_id",
        "category_id",
        "since",
        "recorded_at",
        unique=True,
    ),
)
