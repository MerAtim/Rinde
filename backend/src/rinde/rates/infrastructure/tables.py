"""Histórico propio de cotizaciones (SQLAlchemy Core, ADR-0002).

Una fila por día, par, clase y fuente. La clase es un tipo de dólar o un
mercado, como el Bitcoin (ADR-0029). Las reglas de `Quote` se repiten como
restricciones: una fila escrita sin pasar por el dominio se rechaza igual.

No tiene dueño: las cotizaciones son las mismas para todos los usuarios.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Table,
)

from rinde.shared.infrastructure.database import metadata

exchange_rates = Table(
    "exchange_rates",
    metadata,
    Column("day", Date, nullable=False),
    Column("base", String(3), nullable=False),
    Column("counter", String(3), nullable=False),
    Column("rate_type", String(16), nullable=False),
    Column("source", String(32), nullable=False),
    Column("buy", Numeric(24, 8), nullable=False),
    Column("sell", Numeric(24, 8), nullable=False),
    # Lo que la fuente dice; algunas, para días pasados, no lo informan.
    Column("updated_at", DateTime(timezone=True), nullable=True),
    # Cuándo la trajo Rinde: sirve para auditar de dónde salió cada número.
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    # La clave primaria empieza por el día y el par: cubre la única consulta que hay.
    PrimaryKeyConstraint("day", "base", "counter", "rate_type", "source"),
    CheckConstraint("buy > 0 AND sell > 0", name="positive"),
    CheckConstraint("buy <= sell", name="buy_not_above_sell"),
    CheckConstraint("base <> counter", name="different_currencies"),
    CheckConstraint("base IN ('ARS', 'USD', 'BTC')", name="base_known"),
    CheckConstraint("counter IN ('ARS', 'USD', 'BTC')", name="counter_known"),
    CheckConstraint(
        "rate_type IN ('official', 'mep', 'ccl', 'blue', 'card', 'crypto', 'bitcoin')",
        name="rate_type_known",
    ),
    CheckConstraint(
        "source IN ('dolarapi', 'argentinadatos', 'criptoya', 'kraken', 'bitstamp')",
        name="source_known",
    ),
    # Cada clase cotiza un solo par: los dólares en pesos, el Bitcoin en dólares.
    CheckConstraint(
        "CASE WHEN rate_type = 'bitcoin' THEN base = 'BTC' AND counter = 'USD'"
        " ELSE base = 'USD' AND counter = 'ARS' END",
        name="pair_matches_kind",
    ),
)
