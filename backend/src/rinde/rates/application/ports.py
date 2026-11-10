"""Puertos del módulo de cotizaciones."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from rinde.rates.domain.quote import Quote
from rinde.shared.domain.rate_type import RateType


class RateSourceUnavailableError(Exception):
    """La fuente no respondió, o respondió algo que no se puede usar.

    No es un error de dominio: no sale de la API. Lo atrapa la cadena de
    fuentes para pasar a la siguiente.
    """


@dataclass(frozen=True, slots=True)
class QuoteRequest:
    """Qué tipos de dólar se piden y de qué día.

    `current` dice si es el día de hoy. Hoy la cotización todavía se mueve y
    algunas fuentes solo publican el último valor; un día cerrado ya no cambia.
    """

    day: date
    types: frozenset[RateType]
    current: bool


class RateProvider(Protocol):
    async def quotes(self, request: QuoteRequest) -> dict[RateType, Quote]:
        """Lo que la fuente tenga de lo pedido, y nada más.

        Que falte un tipo significa que la fuente no lo tiene. Si la fuente no
        pudo responder, lanza `RateSourceUnavailableError`.
        """
        ...


class QuoteRepository(Protocol):
    async def for_day(self, day: date, types: frozenset[RateType]) -> list[Quote]:
        """Lo guardado de ese día. Si hay de varias fuentes, una por tipo."""
        ...

    async def add_all(self, quotes: Iterable[Quote], fetched_at: datetime) -> None:
        """Si ya está guardada, se deja la que estaba: un día cerrado no cambia."""
        ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...
