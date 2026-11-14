"""IPC guardado (SQLAlchemy Core, ADR-0002, ADR-0025).

Una fila por mes. Las reglas de `CpiMonth` se repiten como restricciones: una
fila escrita sin pasar por el dominio se rechaza igual.

No tiene dueño: el índice es el mismo para todos los usuarios.
"""

from sqlalchemy import CheckConstraint, Column, Date, DateTime, Numeric, String, Table

from rinde.shared.infrastructure.database import metadata

cpi_months = Table(
    "cpi_months",
    metadata,
    Column("month", Date, primary_key=True),
    Column("value", Numeric(14, 4), nullable=False),
    Column("source", String(16), nullable=False),
    # Cuándo lo trajo Rinde: sirve para auditar de dónde salió cada factor.
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("EXTRACT(DAY FROM month) = 1", name="first_day_of_month"),
    CheckConstraint("value > 0", name="positive"),
    CheckConstraint("source IN ('indec')", name="source_known"),
)
