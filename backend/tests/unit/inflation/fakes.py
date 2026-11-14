"""Piezas en memoria para probar el módulo de inflación."""

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal

from rinde.inflation.application.ports import CpiSourceUnavailableError
from rinde.inflation.domain.cpi import CpiMonth, CpiSource


def cpi(month: date, index: str) -> CpiMonth:
    return CpiMonth(month, Decimal(index), CpiSource.INDEC)


class InMemoryCpi:
    def __init__(self, *months: CpiMonth) -> None:
        self.months: dict[date, CpiMonth] = {m.month: m for m in months}
        self.added: list[tuple[list[CpiMonth], datetime]] = []

    async def for_range(self, since: date, until: date) -> list[CpiMonth]:
        return [self.months[m] for m in sorted(self.months) if since <= m <= until]

    async def latest(self) -> CpiMonth | None:
        return self.months[max(self.months)] if self.months else None

    async def add_all(self, months: Iterable[CpiMonth], fetched_at: datetime) -> None:
        batch = list(months)
        self.added.append((batch, fetched_at))
        for item in batch:
            self.months.setdefault(item.month, item)


class FakeCpiProvider:
    """La serie que devuelve la fuente, o una fuente caída."""

    def __init__(self, *months: CpiMonth, down: bool = False) -> None:
        self.months = list(months)
        self.down = down
        self.calls = 0

    async def series(self) -> list[CpiMonth]:
        self.calls += 1
        if self.down:
            raise CpiSourceUnavailableError
        return list(self.months)
