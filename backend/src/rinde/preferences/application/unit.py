"""Unidad de trabajo de preferencias: los casos de uso de un pedido, con una transacción."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from rinde.preferences.application.use_cases import (
    GetPreferences,
    PreferencesDependencies,
    UpdatePreferences,
)


@dataclass(frozen=True, slots=True)
class PreferencesUnit:
    get: GetPreferences
    update: UpdatePreferences


class PreferencesUnitFactory(Protocol):
    """La raíz de composición elige la implementación: base real o memoria en tests."""

    def __call__(self) -> AbstractAsyncContextManager[PreferencesUnit]: ...


def build_preferences_unit(deps: PreferencesDependencies) -> PreferencesUnit:
    return PreferencesUnit(get=GetPreferences(deps), update=UpdatePreferences(deps))
