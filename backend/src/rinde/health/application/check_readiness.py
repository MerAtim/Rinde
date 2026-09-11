"""Caso de uso: verificar si la API está lista para atender pedidos."""

from dataclasses import dataclass
from typing import Protocol


class DatabaseProbe(Protocol):
    """Puerto: responde si la base de datos está disponible."""

    async def is_reachable(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    database: bool

    @property
    def ready(self) -> bool:
        return self.database


class CheckReadiness:
    def __init__(self, database: DatabaseProbe) -> None:
        self._database = database

    async def execute(self) -> ReadinessReport:
        return ReadinessReport(database=await self._database.is_reachable())
