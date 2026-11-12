"""Puertos de presupuestos.

Las vigencias son propias. Las categorías, el gasto, el tipo de dólar y las
cotizaciones son de otros módulos: se leen por su capa de aplicación, con
adaptadores que arma la raíz de composición (ADR-0001), como hace el dashboard.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from rinde.budgets.domain.budget import BudgetLimit, Converter
from rinde.shared.domain.money import Currency, Money
from rinde.shared.domain.rate_type import RateType


class BudgetRepository(Protocol):
    async def add(self, limit: BudgetLimit) -> None:
        """Agrega una vigencia. Nunca pisa ni borra las anteriores."""
        ...

    async def history(self, owner_id: UUID, until: date) -> list[BudgetLimit]:
        """Las vigencias del dueño que empezaron hasta ese mes, de todas sus categorías."""
        ...


@dataclass(frozen=True, slots=True)
class CategoryInfo:
    id: UUID
    name: str
    slug: str | None
    """Solo en las sembradas: la interfaz las traduce por este identificador (ADR-0011)."""
    is_expense: bool


class CategoryReader(Protocol):
    async def categories(self, owner_id: UUID) -> list[CategoryInfo]:
        """Solo las del dueño: no hay forma de pedir las de otra persona."""
        ...


@dataclass(frozen=True, slots=True)
class CategoryExpense:
    category_id: UUID
    day: date
    money: Money
    """Siempre positivo."""


class SpendingReader(Protocol):
    async def expenses(self, owner_id: UUID, since: date, until: date) -> list[CategoryExpense]:
        """Los gastos del dueño en todas sus cuentas, sumados por día, categoría y moneda.

        Sin transferencias: mover plata entre cuentas propias no es gastar.
        """
        ...


class RateTypeReader(Protocol):
    async def rate_type(self, owner_id: UUID) -> RateType:
        """El dólar con que la persona eligió convertir (ADR-0017)."""
        ...


class ConverterFactory(Protocol):
    async def converter(
        self, target: Currency, rate_type: RateType, since: date, until: date
    ) -> Converter:
        """Con la cotización de cada día del rango ya traída: convertir no consulta nada."""
        ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...
