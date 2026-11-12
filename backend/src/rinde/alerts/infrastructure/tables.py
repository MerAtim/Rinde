"""Tabla de alertas de presupuesto (SQLAlchemy Core), ADR-0022.

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
    UniqueConstraint,
    Uuid,
    text,
)

from rinde.shared.infrastructure.database import metadata

ONCE_PER_MONTH = ("owner_id", "category_id", "month", "threshold")
"""Una alerta por categoría, mes y umbral: evaluar dos veces no repite el aviso."""

budget_alerts = Table(
    "budget_alerts",
    metadata,
    Column("id", Uuid, primary_key=True),
    # El borrado de un usuario borra sus alertas: es el borrado completo de sus datos.
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("category_id", Uuid, nullable=False),
    # Siempre 'expense', como en los presupuestos: la clave foránea pide una
    # categoría de gastos de la misma persona.
    Column("kind", String(8), nullable=False, server_default=text("'expense'")),
    Column("month", Date, nullable=False),
    Column("threshold", String(8), nullable=False),
    # La foto del presupuesto al dispararse, en la moneda del tope.
    Column("limit_amount", Numeric(20, 2), nullable=False),
    Column("spent_amount", Numeric(20, 2), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("raised_at", DateTime(timezone=True), nullable=False),
    Column("read_at", DateTime(timezone=True), nullable=True),
    ForeignKeyConstraint(
        ["category_id", "owner_id", "kind"],
        ["categories.id", "categories.owner_id", "categories.kind"],
        name="category_of_the_same_owner_and_kind",
        # Como los topes, una categoría borrada se lleva sus alertas (ADR-0021).
        ondelete="CASCADE",
    ),
    CheckConstraint("kind = 'expense'", name="kind_is_expense"),
    CheckConstraint("extract(day FROM month) = 1", name="month_first_day"),
    CheckConstraint("threshold IN ('warning', 'over')", name="threshold_allowed"),
    CheckConstraint("limit_amount > 0", name="limit_positive"),
    # Al 80 % de un tope positivo, ya se gastó algo.
    CheckConstraint("spent_amount > 0", name="spent_positive"),
    CheckConstraint("currency IN ('ARS', 'USD')", name="currency_allowed"),
    CheckConstraint("read_at IS NULL OR read_at >= raised_at", name="read_after_raised"),
    UniqueConstraint(*ONCE_PER_MONTH, name="uq_budget_alerts_once_per_month_and_threshold"),
    # Las últimas de una persona, y cuántas tiene sin leer.
    Index("ix_budget_alerts_owner_id_raised_at", "owner_id", "raised_at"),
)
