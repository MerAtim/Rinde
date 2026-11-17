"""Conversión de un monto con una o más cotizaciones (ADR-0017, ADR-0029).

La regla de qué precio se usa, compra o venta, es la de lo que de verdad
podrías hacer en el mercado, y siempre del lado prudente: nunca se valúa de
más lo que tenés ni de menos lo que debés.

* Dólares que tenés, a pesos: los venderías, así que te pagan la **compra**.
* Pesos que tenés, a dólares: los comprarías, así que pagás la **venta**.
* Una deuda, al revés: para cancelar dólares que debés tenés que comprarlos a
  la venta; para cancelar pesos que debés, vender dólares a la compra.
"""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from rinde.rates.domain.errors import ConversionNotSupportedError
from rinde.rates.domain.quote import Quote
from rinde.shared.domain.money import Currency, Money

# Precisión de la cuenta intermedia, antes de redondear al resultado. Sobra para
# 16 dígitos enteros del monto por 16 de la cotización, con 8 decimales cada uno.
_PRECISION = 60


@dataclass(frozen=True, slots=True)
class Step:
    """Un paso de una conversión: la cotización que se usó y el precio que se aplicó."""

    quote: Quote
    rate: Decimal
    """La compra o la venta de `quote`, según el caso."""


@dataclass(frozen=True, slots=True)
class Conversion:
    """El monto original, el convertido y cada paso que hubo para llegar.

    Entre dólares y pesos es un paso. Bitcoin a pesos son dos: a dólares con su
    precio, y a pesos con el dólar elegido (ADR-0029).
    """

    original: Money
    converted: Money
    steps: tuple[Step, ...]


@dataclass(frozen=True, slots=True)
class ExactConversion:
    """La conversión sin redondear, para quien suma muchas antes de redondear una vez."""

    amount: Decimal
    currency: Currency
    steps: tuple[Step, ...]


# Los pares que tienen cotización, en el orden del camino: BTC, USD, ARS.
_CHAIN = (Currency.BTC, Currency.USD, Currency.ARS)


def route(source: Currency, target: Currency) -> tuple[tuple[Currency, Currency], ...]:
    """Los pares (base, counter) por los que pasa un monto para llegar a destino.

    Bitcoin a pesos pasa por el dólar; pesos a Bitcoin, también. Vacío si ya
    está en la moneda de destino.
    """
    start, end = _CHAIN.index(source), _CHAIN.index(target)
    low, high = min(start, end), max(start, end)
    pairs = tuple((_CHAIN[i], _CHAIN[i + 1]) for i in range(low, high))
    return pairs if start <= end else tuple(reversed(pairs))


def _step(amount: Decimal, currency: Currency, quote: Quote) -> tuple[Decimal, Currency, Step]:
    is_asset = amount >= 0
    if currency is quote.base:
        # Dólares a pesos: tenerlos es venderlos (compra); deberlos, comprarlos (venta).
        rate = quote.buy if is_asset else quote.sell
        with localcontext(prec=_PRECISION):
            return amount * rate, quote.counter, Step(quote, rate)
    if currency is quote.counter:
        # Pesos a dólares: tenerlos es comprar dólares (venta); deberlos, venderlos (compra).
        rate = quote.sell if is_asset else quote.buy
        with localcontext(prec=_PRECISION):
            return amount / rate, quote.base, Step(quote, rate)
    raise ConversionNotSupportedError


def convert_exact(money: Money, *quotes: Quote) -> ExactConversion:
    """Convierte pasando por cada cotización, en orden, sin redondear.

    Un reporte suma cientos de conversiones: si redondeara cada una, el error
    de cada redondeo se acumularía. Redondea una sola vez, al final (ADR-0002).
    En cada paso vale la regla prudente, con el signo del monto, que no cambia.
    """
    if not quotes:
        raise ConversionNotSupportedError
    amount, currency = money.amount, money.currency
    steps: list[Step] = []
    for quote in quotes:
        amount, currency, step = _step(amount, currency, quote)
        steps.append(step)
    return ExactConversion(amount, currency, tuple(steps))


def convert(money: Money, *quotes: Quote) -> Conversion:
    """Convierte pasando por cada cotización, en orden.

    El redondeo es uno solo, al final, de banquero y a la precisión de la
    moneda de destino (ADR-0002).
    """
    exact = convert_exact(money, *quotes)
    return Conversion(
        original=money,
        converted=Money.rounded(exact.amount, exact.currency),
        steps=exact.steps,
    )
