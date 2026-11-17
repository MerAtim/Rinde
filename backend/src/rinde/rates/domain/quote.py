"""Cotización de un día: un dólar en pesos, o un mercado (ADR-0002, ADR-0016, ADR-0029).

En Argentina conviven varios dólares el mismo día y la diferencia entre ellos
puede pasar del 30 %. Por eso una cotización siempre dice de qué dólar es, de
qué día y de qué fuente salió: "el dólar" a secas no existe.

El precio del Bitcoin no es un dólar más: es un mercado, el par BTC/USD. Se
separan para que nadie lo pueda elegir como el dólar con que se convierte.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from enum import StrEnum

from rinde.rates.domain.errors import QuoteInvalidError
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType

RATE_DECIMALS = 8
"""Los mismos decimales que la columna `NUMERIC(24, 8)` (ADR-0002)."""

_RATE_QUANTUM = Decimal(1).scaleb(-RATE_DECIMALS)
# NUMERIC(24, 8) deja 16 dígitos enteros. Un valor más grande no entra en la base.
_MAX_RATE = Decimal(10) ** 16


class RateSource(StrEnum):
    """En orden de prioridad, como en la cadena de fuentes de cada par."""

    DOLARAPI = "dolarapi"
    ARGENTINADATOS = "argentinadatos"
    CRIPTOYA = "criptoya"
    KRAKEN = "kraken"
    BITSTAMP = "bitstamp"


class Market(StrEnum):
    """Lo que se cotiza en dólares y no es un dólar: por ahora, el Bitcoin (ADR-0029)."""

    BITCOIN = "bitcoin"


type QuoteKind = RateType | Market
"""Qué cotiza una `Quote`: un tipo de dólar en pesos, o un mercado en dólares."""

ALL_KINDS: tuple[QuoteKind, ...] = (*RateType, *Market)


def pair_of(kind: QuoteKind) -> tuple[Currency, Currency]:
    """El par que cotiza cada clase: (base, counter). Es fijo, y la base lo exige."""
    if isinstance(kind, Market):
        return Currency.BTC, Currency.USD
    return Currency.USD, Currency.ARS


def kind_of(value: str) -> QuoteKind:
    """La clase guardada como texto: un tipo de dólar o un mercado."""
    try:
        return RateType(value)
    except ValueError:
        return Market(value)


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

    rate_type: QuoteKind
    """Un tipo de dólar o un mercado. Se llama así por la columna, que es anterior."""
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
        if (self.base, self.counter) != pair_of(self.rate_type):
            raise QuoteInvalidError
        buy, sell = _exact_rate(self.buy), _exact_rate(self.sell)
        # Comprarle dólares a alguien más barato de lo que te los vende no existe:
        # si una fuente lo dice, la fuente está mal.
        if buy > sell:
            raise QuoteInvalidError
        object.__setattr__(self, "buy", buy)
        object.__setattr__(self, "sell", sell)
