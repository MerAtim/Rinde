"""Conversión de un monto con una cotización (ADR-0017).

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
class Conversion:
    """El monto original, el convertido y la cotización que se usó para llegar."""

    original: Money
    converted: Money
    quote: Quote
    rate: Decimal
    """El precio que se aplicó: la compra o la venta de `quote`."""


@dataclass(frozen=True, slots=True)
class ExactConversion:
    """La conversión sin redondear, para quien suma muchas antes de redondear una vez."""

    amount: Decimal
    currency: Currency
    rate: Decimal


def convert_exact(money: Money, quote: Quote) -> ExactConversion:
    """Convierte a la otra moneda del par de la cotización, sin redondear.

    Un reporte suma cientos de conversiones: si redondeara cada una, el error
    de cada redondeo se acumularía. Redondea una sola vez, al final (ADR-0002).
    """
    is_asset = not money.is_negative
    if money.currency is quote.base:
        # Dólares a pesos: tenerlos es venderlos (compra); deberlos, comprarlos (venta).
        rate = quote.buy if is_asset else quote.sell
        with localcontext(prec=_PRECISION):
            amount = money.amount * rate
        return ExactConversion(amount, quote.counter, rate)
    if money.currency is quote.counter:
        # Pesos a dólares: tenerlos es comprar dólares (venta); deberlos, venderlos (compra).
        rate = quote.sell if is_asset else quote.buy
        with localcontext(prec=_PRECISION):
            amount = money.amount / rate
        return ExactConversion(amount, quote.base, rate)
    raise ConversionNotSupportedError


def convert(money: Money, quote: Quote) -> Conversion:
    """Convierte a la otra moneda del par de la cotización.

    El redondeo es uno solo, al final, de banquero y a la precisión de la
    moneda de destino (ADR-0002).
    """
    exact = convert_exact(money, quote)
    return Conversion(
        original=money,
        converted=Money.rounded(exact.amount, exact.currency),
        quote=quote,
        rate=exact.rate,
    )
