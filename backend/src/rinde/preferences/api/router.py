"""Endpoints de preferencias (ADR-0017).

Sin identificador en el camino: cada persona ve y cambia las suyas, las de la
sesión, y no hay forma de nombrar las de otra.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from rinde.preferences.api.schemas import PreferencesRequest, PreferencesResponse
from rinde.preferences.application.unit import PreferencesUnit, PreferencesUnitFactory
from rinde.shared.api.csrf import CSRF
from rinde.shared.api.identity import CurrentUserId
from rinde.shared.api.schemas import error_responses

router = APIRouter(prefix="/preferences", tags=["preferences"])


async def preferences_unit(request: Request) -> AsyncIterator[PreferencesUnit]:
    factory: PreferencesUnitFactory = request.app.state.preferences_factory
    async with factory() as unit:
        yield unit


Unit = Annotated[PreferencesUnit, Depends(preferences_unit)]


@router.get("", responses=error_responses(401), summary="Ver mis preferencias")
async def get_preferences(user_id: CurrentUserId, unit: Unit) -> PreferencesResponse:
    return PreferencesResponse.from_preferences(await unit.get.execute(user_id))


@router.put(
    "",
    dependencies=CSRF,
    responses=error_responses(401, 403, 422),
    summary="Cambiar mis preferencias",
)
async def update_preferences(
    payload: PreferencesRequest, user_id: CurrentUserId, unit: Unit
) -> PreferencesResponse:
    preferences = await unit.update.execute(user_id, payload.reference_currency, payload.rate_type)
    return PreferencesResponse.from_preferences(preferences)
