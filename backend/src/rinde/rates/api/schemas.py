"""Esquemas de salida de cotizaciones.

Compra y venta viajan como string decimal (ADR-0002): un número en JSON pasa
por el `double` de JavaScript y deja de ser exacto.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from rinde.rates.domain.conversion import Conversion
from rinde.rates.domain.quote import Market, Quote, RateSource
from rinde.shared.api.schemas import MoneyResponse, decimal_text
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType

RateOut = Annotated[Decimal, PlainSerializer(decimal_text, return_type=str)]


class QuoteResponse(BaseModel):
    rate_type: RateType | Market = Field(
        description="Un tipo de dólar, o un mercado como el Bitcoin (ADR-0029)"
    )
    base: Currency
    counter: Currency
    day: date = Field(description="Día al que corresponde, en Argentina")
    buy: RateOut = Field(description="Cuánto de counter se recibe por un base")
    sell: RateOut = Field(description="Cuánto de counter se paga por un base")
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


class ConversionQuery(BaseModel):
    """Qué convertir, como parámetros de consulta."""

    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(description='Monto como string decimal, por ejemplo "1500.00"')
    currency: Currency
    target: Currency
    day: date | None = Field(default=None, description="Día en Argentina. Si falta, hoy")


class ConversionStepResponse(BaseModel):
    rate: RateOut = Field(description="El precio que se aplicó: la compra o la venta (ADR-0017)")
    quote: QuoteResponse


class ConversionResponse(BaseModel):
    original: MoneyResponse
    converted: MoneyResponse
    steps: list[ConversionStepResponse] = Field(
        description="Cada cotización por la que pasó el monto, en orden. Bitcoin a pesos son dos"
    )

    @classmethod
    def from_conversion(cls, conversion: Conversion) -> ConversionResponse:
        return cls(
            original=MoneyResponse.from_money(conversion.original),
            converted=MoneyResponse.from_money(conversion.converted),
            steps=[
                ConversionStepResponse(rate=step.rate, quote=QuoteResponse.from_quote(step.quote))
                for step in conversion.steps
            ],
        )
