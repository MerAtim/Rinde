"""Casos de uso de preferencias. Todos reciben el dueño: es el filtro de autorización."""

from dataclasses import dataclass
from uuid import UUID

from rinde.preferences.application.ports import Clock, PreferencesRepository, Transaction
from rinde.preferences.domain.preferences import Preferences
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType


@dataclass(frozen=True, slots=True)
class PreferencesDependencies:
    preferences: PreferencesRepository
    transaction: Transaction
    clock: Clock


class GetPreferences:
    """Las guardadas o, si nunca cambió nada, las de por defecto. Nunca falla por no tenerlas."""

    def __init__(self, deps: PreferencesDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID) -> Preferences:
        stored = await self._deps.preferences.get(owner_id)
        return stored or Preferences.defaults(owner_id)


class UpdatePreferences:
    def __init__(self, deps: PreferencesDependencies) -> None:
        self._deps = deps

    async def execute(
        self, owner_id: UUID, reference_currency: Currency, rate_type: RateType
    ) -> Preferences:
        preferences = Preferences(
            owner_id, reference_currency, rate_type, updated_at=self._deps.clock.now()
        )
        await self._deps.preferences.save(preferences)
        await self._deps.transaction.commit()
        return preferences
