"""Cotización del dólar en pesos para un día (ADR-0002, ADR-0016).

En Argentina conviven varios dólares el mismo día y la diferencia entre ellos
puede pasar del 30 %. Por eso una cotización siempre dice de qué dólar es, de
qué día y de qué fuente salió: "el dólar" a secas no existe.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from enum import StrEnum
from zoneinfo import ZoneInfo

from rinde.rates.domain.errors import QuoteInvalidError
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType

ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")

RATE_DECIMALS = 8
"""Los mismos decimales que la columna `NUMERIC(24, 8)` (ADR-0002)."""

_RATE_QUANTUM = Decimal(1).scaleb(-RATE_DECIMALS)
# NUMERIC(24, 8) deja 16 dígitos enteros. Un valor más grande no entra en la base.
_MAX_RATE = Decimal(10) ** 16


class RateSource(StrEnum):
    DOLARAPI = "dolarapi"
    ARGENTINADATOS = "argentinadatos"
    CRIPTOYA = "criptoya"


def argentine_day(moment: datetime) -> date:
    """El día en Argentina. Las fuentes publican por día argentino, no por día UTC.

    A las 22 de Buenos Aires ya es el día siguiente en UTC: con la fecha UTC se
    pediría la cotización de un día que todavía no empezó.
    """
    if moment.tzinfo is None:
        msg = "el momento tiene que tener zona horaria"
        raise ValueError(msg)
    return moment.astimezone(ARGENTINA).date()


def round_rate(value: Decimal) -> Decimal:
    """Redondeo explícito para el borde: lo que llega de una fuente con más de 8 decimales."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise QuoteInvalidError
    try:
        return value.quantize(_RATE_QUANTUM, rounding=ROUND_HALF_EVEN)
    except InvalidOperation:
        raise QuoteInvalidError from None


def _exact_rate(value: object) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise QuoteInvalidError
    if not Decimal(0) < value < _MAX_RATE:
        raise QuoteInvalidError
    exact = value.quantize(_RATE_QUANTUM)
    if exact != value:
        # Igual que con `Money`: no se redondea en silencio. Para eso está `round_rate`.
        raise QuoteInvalidError
    return exact


@dataclass(frozen=True, slots=True)
class Quote:
    """Cuántos `counter` se pagan (venta) o se reciben (compra) por un `base`.

    `day` es el día al que corresponde la cotización. `updated_at` es el momento
    en que la fuente dice que la actualizó, si lo informa: un feriado, el oficial
    de hoy puede ser el del último día hábil, y eso se muestra, no se esconde.
    """

    rate_type: RateType
    day: date
    buy: Decimal
    sell: Decimal
    source: RateSource
    updated_at: datetime | None = None
    base: Currency = Currency.USD
    counter: Currency = Currency.ARS

    def __post_init__(self) -> None:
        # datetime es subclase de date: un momento no es un día.
        if not isinstance(self.day, date) or isinstance(self.day, datetime):
            raise QuoteInvalidError
        if self.updated_at is not None and self.updated_at.tzinfo is None:
            raise QuoteInvalidError
        if self.base is self.counter:
            raise QuoteInvalidError
        buy, sell = _exact_rate(self.buy), _exact_rate(self.sell)
        # Comprarle dólares a alguien más barato de lo que te los vende no existe:
        # si una fuente lo dice, la fuente está mal.
        if buy > sell:
            raise QuoteInvalidError
        object.__setattr__(self, "buy", buy)
        object.__setattr__(self, "sell", sell)
