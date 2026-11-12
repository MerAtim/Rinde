"""Puertos de alertas.

Las alertas son propias. El avance de los presupuestos y los nombres de las
categorías son de otros módulos: se leen por su capa de aplicación, con
adaptadores que arma la raíz de composición, como hace presupuestos.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from rinde.alerts.domain.alert import BudgetAlert, Threshold
from rinde.shared.domain.money import Money


class AlertRepository(Protocol):
    async def add(self, alert: BudgetAlert) -> bool:
        """Guarda la alerta. `False` si ya había una igual: no se repite (ADR-0022)."""
        ...

    async def raised_in(self, owner_id: UUID, month: date) -> dict[UUID, set[Threshold]]:
        """Los umbrales ya avisados en ese mes, por categoría."""
        ...

    async def latest(self, owner_id: UUID, limit: int) -> list[BudgetAlert]:
        """Las últimas, de la más nueva a la más vieja. Solo las del dueño."""
        ...

    async def unread_count(self, owner_id: UUID) -> int: ...

    async def mark_read(self, owner_id: UUID, ids: Collection[UUID], at: datetime) -> None:
        """Las que no son del dueño, o ya estaban leídas, no cambian."""
        ...


@dataclass(frozen=True, slots=True)
class BudgetReading:
    """Cómo está el presupuesto de una categoría, según el módulo de presupuestos."""

    category_id: UUID
    limit: Money
    spent: Money
    reached: Threshold | None
    """El umbral al que llegó lo gastado, o `None` si no llegó a ninguno."""


@dataclass(frozen=True, slots=True)
class MonthReading:
    month: date
    budgets: list[BudgetReading]


class BudgetReader(Protocol):
    async def current_month(self, owner_id: UUID) -> MonthReading:
        """El mes en curso de Argentina, medido como lo muestra la pantalla de presupuestos."""
        ...


@dataclass(frozen=True, slots=True)
class CategoryInfo:
    id: UUID
    name: str
    slug: str | None
    """Solo en las sembradas: la interfaz las traduce por este identificador (ADR-0011)."""


class CategoryReader(Protocol):
    async def categories(self, owner_id: UUID) -> list[CategoryInfo]:
        """Solo las del dueño."""
        ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...
