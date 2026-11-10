"""Tabla de preferencias (SQLAlchemy Core): una fila por persona, solo si cambió algo."""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String, Table, Uuid

from rinde.shared.infrastructure.database import metadata

user_preferences = Table(
    "user_preferences",
    metadata,
    # El borrado de un usuario borra sus preferencias: es el borrado completo de sus datos.
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("reference_currency", String(3), nullable=False),
    Column("rate_type", String(16), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("reference_currency IN ('ARS', 'USD')", name="reference_currency_known"),
    CheckConstraint(
        "rate_type IN ('official', 'mep', 'ccl', 'blue', 'card', 'crypto')", name="rate_type_known"
    ),
)
