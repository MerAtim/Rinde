"""Puertos del módulo de preferencias.

El repositorio solo busca por dueño: no hay otra forma de pedir unas
preferencias, así que no hay forma de pedir las de otra persona.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from rinde.preferences.domain.preferences import Preferences


class PreferencesRepository(Protocol):
    async def get(self, owner_id: UUID) -> Preferences | None: ...

    async def save(self, preferences: Preferences) -> None:
        """Crea o reemplaza: una persona tiene una sola fila de preferencias."""
        ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...
