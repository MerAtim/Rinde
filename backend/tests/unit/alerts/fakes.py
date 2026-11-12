"""Piezas en memoria para probar alertas sin otros módulos."""

from collections import defaultdict
from collections.abc import Collection
from dataclasses import replace
from datetime import date, datetime
from uuid import UUID

from rinde.alerts.application.ports import CategoryInfo, MonthReading
from rinde.alerts.domain.alert import BudgetAlert, Threshold


class InMemoryAlertRepository:
    """Con la misma regla que la restricción única de la base."""

    def __init__(self) -> None:
        self.rows: list[BudgetAlert] = []

    async def add(self, alert: BudgetAlert) -> bool:
        key = (alert.owner_id, alert.category_id, alert.month, alert.threshold)
        if any(
            (row.owner_id, row.category_id, row.month, row.threshold) == key for row in self.rows
        ):
            return False
        self.rows.append(alert)
        return True

    async def raised_in(self, owner_id: UUID, month: date) -> dict[UUID, set[Threshold]]:
        raised: defaultdict[UUID, set[Threshold]] = defaultdict(set)
        for row in self.rows:
            if row.owner_id == owner_id and row.month == month:
                raised[row.category_id].add(row.threshold)
        return dict(raised)

    async def latest(self, owner_id: UUID, limit: int) -> list[BudgetAlert]:
        mine = [row for row in self.rows if row.owner_id == owner_id]
        mine.sort(key=lambda row: (row.raised_at, row.id), reverse=True)
        return mine[:limit]

    async def unread_count(self, owner_id: UUID) -> int:
        return sum(1 for row in self.rows if row.owner_id == owner_id and not row.is_read)

    async def mark_read(self, owner_id: UUID, ids: Collection[UUID], at: datetime) -> None:
        self.rows = [
            replace(row, read_at=at)
            if row.owner_id == owner_id and row.id in ids and not row.is_read
            else row
            for row in self.rows
        ]


class FixedBudgets:
    """Lo que diría presupuestos del mes en curso; se puede cambiar entre evaluaciones."""

    def __init__(self, owner_id: UUID, reading: MonthReading) -> None:
        self._owner_id = owner_id
        self.reading = reading
        self.calls = 0

    async def current_month(self, owner_id: UUID) -> MonthReading:
        self.calls += 1
        if owner_id != self._owner_id:
            return MonthReading(self.reading.month, [])
        return self.reading


class FixedCategories:
    def __init__(self, owner_id: UUID, *categories: CategoryInfo) -> None:
        self._owner_id = owner_id
        self.items = list(categories)

    async def categories(self, owner_id: UUID) -> list[CategoryInfo]:
        return list(self.items) if owner_id == self._owner_id else []
