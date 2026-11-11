"""Endpoint del dashboard (ADR-0018).

Solo lectura, así que no pide el encabezado CSRF. No hay identificador en el
camino: todo se resume para la persona de la sesión, y una cuenta ajena en el
filtro no agrega nada (ADR-0009).
"""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from rinde.dashboard.api.schemas import DashboardQuery, DashboardResponse, parse_month
from rinde.dashboard.application.use_cases import GetDashboard
from rinde.shared.api.identity import CurrentUserId
from rinde.shared.api.schemas import error_responses

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", responses=error_responses(401, 422), summary="Ver mi dashboard")
async def get_dashboard(
    request: Request, user_id: CurrentUserId, query: Annotated[DashboardQuery, Query()]
) -> DashboardResponse:
    """Gasto por categoría, flujo de cada mes y patrimonio, en la moneda de referencia.

    Lo que no se puede convertir no entra en los totales: sale en `unconverted`.
    """
    dashboard: GetDashboard = request.app.state.dashboard
    result = await dashboard.execute(
        user_id,
        first=parse_month(query.first),
        last=parse_month(query.last),
        account_ids=frozenset(query.account) or None,
    )
    return DashboardResponse.from_dashboard(result)
