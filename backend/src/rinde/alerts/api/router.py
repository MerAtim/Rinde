"""Endpoints de alertas (ADR-0022).

Las alertas no se crean por la API: las dispara un gasto. Acá solo se leen y
se marcan como leídas, siempre las del usuario autenticado.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from rinde.alerts.api.schemas import AlertsResponse, MarkReadRequest
from rinde.alerts.application.unit import AlertsUnit, AlertsUnitFactory
from rinde.shared.api.csrf import CSRF
from rinde.shared.api.identity import CurrentUserId
from rinde.shared.api.schemas import error_responses

router = APIRouter(prefix="/alerts", tags=["alerts"])


async def alerts_unit(request: Request) -> AsyncIterator[AlertsUnit]:
    factory: AlertsUnitFactory = request.app.state.alerts_factory
    async with factory() as unit:
        yield unit


Unit = Annotated[AlertsUnit, Depends(alerts_unit)]


@router.get("", responses=error_responses(401), summary="Ver mis alertas")
async def list_alerts(user_id: CurrentUserId, unit: Unit) -> AlertsResponse:
    """Las últimas alertas de presupuesto y cuántas hay sin leer."""
    return AlertsResponse.from_feed(await unit.list.execute(user_id))


@router.post(
    "/read",
    dependencies=CSRF,
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 403, 422),
    summary="Marcar alertas como leídas",
)
async def mark_read(payload: MarkReadRequest, user_id: CurrentUserId, unit: Unit) -> Response:
    """Repetirlo no cambia nada: una alerta leída sigue con su primera fecha de lectura."""
    await unit.mark_read.execute(user_id, set(payload.ids))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
