"""Caso de uso de inflación: el IPC de un rango de meses y el último publicado (ADR-0025)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from rinde.inflation.application.ports import (
    Clock,
    CpiProvider,
    CpiRepository,
    CpiSourceUnavailableError,
    Transaction,
)
from rinde.inflation.domain.cpi import CpiMonth
from rinde.inflation.domain.errors import CpiRangeInvalidError
from rinde.shared.domain.calendar import argentine_day


@dataclass(frozen=True, slots=True)
class InflationDependencies:
    months: CpiRepository
    provider: CpiProvider
    transaction: Transaction
    clock: Clock


@dataclass(frozen=True, slots=True)
class CpiTable:
    months: dict[date, CpiMonth]
    """Los meses del rango que tienen índice. Un mes que falta no está publicado."""
    base: CpiMonth | None
    """El último mes publicado, esté o no en el rango. `None` si no hay ninguno."""


def _shift(month: date, months: int) -> date:
    index = month.year * 12 + month.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _months(first: date, last: date) -> list[date]:
    count = (last.year - first.year) * 12 + last.month - first.month + 1
    return [_shift(first, offset) for offset in range(count)]


class GetCpi:
    """El IPC de cada mes de un rango, y el mes base.

    * Sale de la base. Si falta un mes que ya debería estar publicado, o lo
      último guardado es anterior al mes pasado, se trae la serie completa en
      un solo pedido y se guarda lo que faltaba.
    * Si la fuente no responde, sirve lo guardado: el mes que falta queda
      afuera, y quien lo usa lo muestra vacío.
    """

    def __init__(self, deps: InflationDependencies) -> None:
        self._deps = deps

    async def execute(self, since: date, until: date) -> CpiTable:
        first, last = since.replace(day=1), until.replace(day=1)
        if first > last:
            raise CpiRangeInvalidError
        now = self._deps.clock.now()
        current = argentine_day(now).replace(day=1)
        # El mes en curso nunca está publicado; el pasado, recién a mediados de este.
        last_closed = _shift(current, -1)

        stored = {cpi.month: cpi for cpi in await self._deps.months.for_range(first, last)}
        base = await self._deps.months.latest()
        expected = _months(first, min(last, last_closed))
        if (
            any(month not in stored for month in expected)
            or base is None
            or base.month < last_closed
        ):

            def missing(cpi: CpiMonth) -> bool:
                """Un mes del rango que no estaba, o uno más nuevo que el último guardado."""
                in_range = first <= cpi.month <= last and cpi.month not in stored
                return in_range or base is None or cpi.month > base.month

            added = await self._load(now, current, missing)
            stored |= {cpi.month: cpi for cpi in added if first <= cpi.month <= last}
            if added:
                newest = max(added, key=lambda cpi: cpi.month)
                if base is None or newest.month > base.month:
                    base = newest
        return CpiTable(months=dict(sorted(stored.items())), base=base)

    async def _load(
        self, now: datetime, current: date, missing: Callable[[CpiMonth], bool]
    ) -> list[CpiMonth]:
        try:
            series = await self._deps.provider.series()
        except CpiSourceUnavailableError:
            return []
        # Solo meses cerrados que faltaban: lo guardado no se pisa, y un mes en
        # curso o futuro no puede estar publicado.
        found = {cpi.month: cpi for cpi in series if cpi.month < current and missing(cpi)}
        if found:
            await self._deps.months.add_all(found.values(), now)
            await self._deps.transaction.commit()
        return list(found.values())
