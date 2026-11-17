"""El precio del Bitcoin se guarda junto a los dólares (ADR-0029).

Suma la clase `bitcoin` y las fuentes Kraken y Bitstamp, y exige que cada clase
cotice su par: los dólares en pesos, el Bitcoin en dólares.

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "exchange_rates"
_DOLLARS = "'official', 'mep', 'ccl', 'blue', 'card', 'crypto'"
_DOLLAR_SOURCES = "'dolarapi', 'argentinadatos', 'criptoya'"


def _replace(name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{_TABLE}_{name}"), _TABLE, type_="check")
    op.create_check_constraint(op.f(f"ck_{_TABLE}_{name}"), _TABLE, condition)


def upgrade() -> None:
    _replace("rate_type_known", f"rate_type IN ({_DOLLARS}, 'bitcoin')")
    _replace("source_known", f"source IN ({_DOLLAR_SOURCES}, 'kraken', 'bitstamp')")
    op.create_check_constraint(
        op.f(f"ck_{_TABLE}_pair_matches_kind"),
        _TABLE,
        "CASE WHEN rate_type = 'bitcoin' THEN base = 'BTC' AND counter = 'USD'"
        " ELSE base = 'USD' AND counter = 'ARS' END",
    )


def downgrade() -> None:
    # Sin la clase, los precios guardados del Bitcoin no tienen lugar.
    op.execute("DELETE FROM exchange_rates WHERE rate_type = 'bitcoin'")
    op.drop_constraint(op.f(f"ck_{_TABLE}_pair_matches_kind"), _TABLE, type_="check")
    _replace("source_known", f"source IN ({_DOLLAR_SOURCES})")
    _replace("rate_type_known", f"rate_type IN ({_DOLLARS})")
