"""Puertos del módulo de inflación."""

from collections.abc import Iterable
from datetime import date, datetime
from typing import Protocol

from rinde.inflation.domain.cpi import CpiMonth


class CpiSourceUnavailableError(Exception):
    """La fuente no respondió, o respondió algo que no se puede usar.

    No es un error de dominio: no sale de la API. Lo atrapa el caso de uso para
    seguir con lo guardado.
    """


class CpiProvider(Protocol):
    async def series(self) -> list[CpiMonth]:
        """Todos los meses publicados, en un solo pedido, ordenados por mes.

        Si la fuente no pudo responder, lanza `CpiSourceUnavailableError`.
        """
        ...


class CpiRepository(Protocol):
    async def for_range(self, since: date, until: date) -> list[CpiMonth]:
        """Lo guardado entre los dos meses, incluidos, ordenado por mes."""
        ...

    async def latest(self) -> CpiMonth | None:
        """El último mes guardado: el mes base de los pesos constantes."""
        ...

    async def add_all(self, months: Iterable[CpiMonth], fetched_at: datetime) -> None:
        """Si un mes ya está guardado, se deja el que estaba: lo publicado no se pisa."""
        ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...
