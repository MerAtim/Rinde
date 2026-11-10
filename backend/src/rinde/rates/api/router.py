"""Endpoints de cotizaciones (ADR-0016).

Solo lectura, así que no piden el encabezado CSRF. Sí piden sesión: sin ella
cualquiera podría usar Rinde para consultar las fuentes sin límite.
"""

from collections.abc import AsyncIterator
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from rinde.rates.api.schemas import ConversionQuery, ConversionResponse, QuoteResponse
from rinde.rates.application.unit import RatesUnit, RatesUnitFactory
from rinde.shared.api.identity import CurrentUserId
from rinde.shared.api.schemas import error_responses
from rinde.shared.domain.money import Money
from rinde.shared.domain.rate_type import RateType

router = APIRouter(prefix="/rates", tags=["rates"])


async def rates_unit(request: Request) -> AsyncIterator[RatesUnit]:
    factory: RatesUnitFactory = request.app.state.rates_factory
    async with factory() as unit:
        yield unit


Unit = Annotated[RatesUnit, Depends(rates_unit)]
Day = Annotated[date | None, Query(description="Día en Argentina. Si falta, hoy")]


@router.get(
    "",
    responses=error_responses(401, 422, 503),
    summary="Cotizaciones del dólar de un día",
)
async def list_rates(_: CurrentUserId, unit: Unit, day: Day = None) -> list[QuoteResponse]:
    """Los tipos que ninguna fuente tiene ese día no aparecen: no se inventan."""
    return [QuoteResponse.from_quote(quote) for quote in await unit.list.execute(day)]


@router.get(
    "/{rate_type}",
    responses=error_responses(401, 404, 422, 503),
    summary="Un tipo de dólar de un día",
)
async def get_rate(
    rate_type: RateType, _: CurrentUserId, unit: Unit, day: Day = None
) -> QuoteResponse:
    return QuoteResponse.from_quote(await unit.get.execute(rate_type, day))


@router.get(
    "/{rate_type}/conversion",
    responses=error_responses(401, 404, 422, 503),
    summary="Convertir un monto con un tipo de dólar",
)
async def convert_amount(
    rate_type: RateType,
    _: CurrentUserId,
    unit: Unit,
    query: Annotated[ConversionQuery, Query()],
) -> ConversionResponse:
    """Con la compra o la venta según el caso, del lado prudente (ADR-0017)."""
    conversion = await unit.convert.execute(
        Money(query.amount, query.currency), query.target, rate_type, query.day
    )
    return ConversionResponse.from_conversion(conversion)
