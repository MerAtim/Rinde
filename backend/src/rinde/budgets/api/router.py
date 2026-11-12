"""Endpoints de presupuestos (ADR-0021).

El tope se nombra por su categoría: una categoría tiene a lo sumo un tope por
mes. Una categoría de otra persona responde 404, igual que una que no existe
(ADR-0009). Fijar es un PUT: repetirlo con el mismo tope no cambia nada, así
que no hace falta `Idempotency-Key`.
"""

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from rinde.budgets.api.schemas import (
    BudgetLimitResponse,
    BudgetRequest,
    BudgetsQuery,
    BudgetsResponse,
    parse_month,
)
from rinde.budgets.application.unit import BudgetsUnit, BudgetsUnitFactory
from rinde.shared.api.csrf import CSRF
from rinde.shared.api.identity import CurrentUserId
from rinde.shared.api.schemas import error_responses

router = APIRouter(prefix="/budgets", tags=["budgets"])


async def budgets_unit(request: Request) -> AsyncIterator[BudgetsUnit]:
    factory: BudgetsUnitFactory = request.app.state.budgets_factory
    async with factory() as unit:
        yield unit


Unit = Annotated[BudgetsUnit, Depends(budgets_unit)]


@router.get("", responses=error_responses(401, 422), summary="Ver mis presupuestos de un mes")
async def list_budgets(
    user_id: CurrentUserId, unit: Unit, query: Annotated[BudgetsQuery, Query()]
) -> BudgetsResponse:
    """El tope de cada categoría en ese mes, cuánto se gastó y cuánto queda."""
    result = await unit.get.execute(user_id, parse_month(query.month))
    return BudgetsResponse.from_month(result)


@router.put(
    "/{category_id}",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404, 422),
    summary="Fijar el tope de una categoría desde este mes",
)
async def set_budget(
    category_id: UUID, payload: BudgetRequest, user_id: CurrentUserId, unit: Unit
) -> BudgetLimitResponse:
    limit = payload.limit()
    vigency = await unit.set.execute(user_id, category_id, limit)
    return BudgetLimitResponse.from_limit(vigency, limit)


@router.delete(
    "/{category_id}",
    dependencies=CSRF,
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 403, 404),
    summary="Quitar el tope de una categoría desde este mes",
)
async def remove_budget(category_id: UUID, user_id: CurrentUserId, unit: Unit) -> Response:
    await unit.remove.execute(user_id, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
