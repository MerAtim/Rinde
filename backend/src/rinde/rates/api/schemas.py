"""Esquemas de salida de cotizaciones.

Compra y venta viajan como string decimal (ADR-0002): un número en JSON pasa
por el `double` de JavaScript y deja de ser exacto.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from rinde.rates.domain.conversion import Conversion
from rinde.rates.domain.quote import Quote, RateSource
from rinde.shared.domain.money import Currency, Money
from rinde.shared.domain.rate_type import RateType

RateOut = Annotated[Decimal, PlainSerializer(str, return_type=str)]


class QuoteResponse(BaseModel):
    rate_type: RateType
    base: Currency
    counter: Currency
    day: date = Field(description="Día al que corresponde, en Argentina")
    buy: RateOut = Field(description="Pesos que se reciben por un dólar")
    sell: RateOut = Field(description="Pesos que se pagan por un dólar")
    source: RateSource
    updated_at: datetime | None = Field(
        description="Cuándo la actualizó la fuente. Un feriado, puede ser de un día hábil anterior"
    )

    @classmethod
    def from_quote(cls, quote: Quote) -> QuoteResponse:
        return cls(
            rate_type=quote.rate_type,
            base=quote.base,
            counter=quote.counter,
            day=quote.day,
            buy=quote.buy,
            sell=quote.sell,
            source=quote.source,
            updated_at=quote.updated_at,
        )


AmountOut = Annotated[Decimal, PlainSerializer(str, return_type=str)]


class ConversionQuery(BaseModel):
    """Qué convertir, como parámetros de consulta."""

    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(description='Monto como string decimal, por ejemplo "1500.00"')
    currency: Currency
    target: Currency
    day: date | None = Field(default=None, description="Día en Argentina. Si falta, hoy")


class MoneyResponse(BaseModel):
    amount: AmountOut
    currency: Currency

    @classmethod
    def from_money(cls, money: Money) -> MoneyResponse:
        return cls(amount=money.amount, currency=money.currency)


class ConversionResponse(BaseModel):
    original: MoneyResponse
    converted: MoneyResponse
    rate: RateOut = Field(description="El precio que se aplicó: la compra o la venta (ADR-0017)")
    quote: QuoteResponse

    @classmethod
    def from_conversion(cls, conversion: Conversion) -> ConversionResponse:
        return cls(
            original=MoneyResponse.from_money(conversion.original),
            converted=MoneyResponse.from_money(conversion.converted),
            rate=conversion.rate,
            quote=QuoteResponse.from_quote(conversion.quote),
        )
