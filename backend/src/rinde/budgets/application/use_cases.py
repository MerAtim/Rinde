"""Casos de uso de presupuestos. Todos reciben el dueño: es el filtro de autorización.

Un cambio vale desde el mes en curso, el de Argentina. No se puede cambiar el
tope de un mes que ya pasó: esa historia queda como fue (ADR-0021).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

from rinde.budgets.application.ports import (
    BudgetRepository,
    CategoryExpense,
    CategoryInfo,
    CategoryReader,
    Clock,
    ConverterFactory,
    RateTypeReader,
    SpendingReader,
    Transaction,
)
from rinde.budgets.domain.budget import (
    BUDGET_CURRENCIES,
    BudgetLimit,
    BudgetProgress,
    Converter,
    Expense,
    latest_in,
    limits_in,
    month_end,
    month_of,
)
from rinde.budgets.domain.errors import (
    BudgetCategoryNotExpenseError,
    BudgetCategoryNotFoundError,
    BudgetMonthInvalidError,
    BudgetNotFoundError,
)
from rinde.shared.domain.calendar import argentine_day
from rinde.shared.domain.money import Currency, Money
from rinde.shared.domain.rate_type import RateType


@dataclass(frozen=True, slots=True)
class BudgetsDependencies:
    budgets: BudgetRepository
    transaction: Transaction
    categories: CategoryReader
    spending: SpendingReader
    rate_types: RateTypeReader
    converters: ConverterFactory
    clock: Clock


def _today(deps: BudgetsDependencies) -> date:
    return argentine_day(deps.clock.now())


def _recorded_after(deps: BudgetsDependencies, current: BudgetLimit | None) -> datetime:
    """Ahora, pero siempre después de la vigencia anterior de la categoría.

    Dos cambios en el mismo instante empatarían, y no se sabría cuál vale. Así
    las vigencias de una categoría quedan en un orden estricto, y la base lo
    exige con una restricción única.
    """
    now = deps.clock.now()
    if current is None or now > current.recorded_at:
        return now
    return current.recorded_at + timedelta(microseconds=1)


async def _expense_category(
    deps: BudgetsDependencies, owner_id: UUID, category_id: UUID
) -> CategoryInfo:
    category = next(
        (item for item in await deps.categories.categories(owner_id) if item.id == category_id),
        None,
    )
    if category is None:
        raise BudgetCategoryNotFoundError
    if not category.is_expense:
        raise BudgetCategoryNotExpenseError
    return category


class SetBudget:
    """Fija el tope de una categoría desde el mes en curso."""

    def __init__(self, deps: BudgetsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, category_id: UUID, limit: Money) -> BudgetLimit:
        deps = self._deps
        await _expense_category(deps, owner_id, category_id)
        month = month_of(_today(deps))
        current = latest_in(await deps.budgets.history(owner_id, month), month).get(category_id)
        # Pedir el mismo tope dos veces no agrega una vigencia: el PUT es idempotente.
        if current is not None and current.limit == limit:
            return current
        created = BudgetLimit(
            id=uuid4(),
            owner_id=owner_id,
            category_id=category_id,
            since=month,
            limit=limit,
            recorded_at=_recorded_after(deps, current),
        )
        await deps.budgets.add(created)
        await deps.transaction.commit()
        return created


class RemoveBudget:
    """Quita el tope desde el mes en curso. Los meses pasados lo conservan."""

    def __init__(self, deps: BudgetsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, category_id: UUID) -> None:
        deps = self._deps
        await _expense_category(deps, owner_id, category_id)
        month = month_of(_today(deps))
        current = latest_in(await deps.budgets.history(owner_id, month), month).get(category_id)
        if current is None or current.limit is None:
            raise BudgetNotFoundError
        await deps.budgets.add(
            BudgetLimit(
                id=uuid4(),
                owner_id=owner_id,
                category_id=category_id,
                since=month,
                limit=None,
                recorded_at=_recorded_after(deps, current),
            )
        )
        await deps.transaction.commit()


@dataclass(frozen=True, slots=True)
class BudgetItem:
    category: CategoryInfo
    since: date
    """El mes desde el que vale este tope."""
    progress: BudgetProgress


@dataclass(frozen=True, slots=True)
class BudgetMonth:
    month: date
    rate_type: RateType
    """El dólar con que se convirtió lo que estaba en otra moneda."""
    items: list[BudgetItem]


class GetBudgets:
    """El avance de cada presupuesto en un mes: el actual, o uno que ya pasó."""

    def __init__(self, deps: BudgetsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, month: date | None = None) -> BudgetMonth:
        deps = self._deps
        today = _today(deps)
        current = month_of(today)
        month = current if month is None else month_of(month)
        if month > current:
            raise BudgetMonthInvalidError
        rate_type = await deps.rate_types.rate_type(owner_id)
        limits = limits_in(await deps.budgets.history(owner_id, month), month)
        if not limits:
            return BudgetMonth(month, rate_type, [])

        # Una categoría borrada se lleva sus topes (ADR-0021); si el borrado llegó
        # mientras se leía, la vigencia huérfana no se muestra.
        categories = {item.id: item for item in await deps.categories.categories(owner_id)}
        limits = {key: value for key, value in limits.items() if key in categories}
        until = min(month_end(month), today)
        by_category: defaultdict[UUID, list[CategoryExpense]] = defaultdict(list)
        for expense in await deps.spending.expenses(owner_id, month, until):
            if expense.category_id in limits:
                by_category[expense.category_id].append(expense)

        converters = await self._converters(limits, by_category, rate_type, month, until)
        items = []
        for category_id, vigency in limits.items():
            limit = vigency.limit
            if limit is None:  # limits_in ya las descartó; esto lo dice para el tipado.
                continue
            progress = BudgetProgress.measure(
                limit,
                [Expense(item.day, item.money) for item in by_category[category_id]],
                converters.get(limit.currency),
            )
            items.append(BudgetItem(categories[category_id], vigency.since, progress))
        items.sort(key=lambda item: item.category.name.casefold())
        return BudgetMonth(month, rate_type, items)

    async def _converters(
        self,
        limits: dict[UUID, BudgetLimit],
        by_category: dict[UUID, list[CategoryExpense]],
        rate_type: RateType,
        since: date,
        until: date,
    ) -> dict[Currency, Converter]:
        """Solo se buscan cotizaciones si algún gasto está en otra moneda convertible."""
        targets = {
            vigency.limit.currency
            for category_id, vigency in limits.items()
            if vigency.limit is not None
            for expense in by_category.get(category_id, [])
            if expense.money.currency is not vigency.limit.currency
            and expense.money.currency in BUDGET_CURRENCIES
        }
        return {
            target: await self._deps.converters.converter(target, rate_type, since, until)
            for target in sorted(targets)
        }
