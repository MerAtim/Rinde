"""Piezas en memoria para probar presupuestos sin otros módulos."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from rinde.budgets.application.ports import CategoryExpense, CategoryInfo
from rinde.budgets.domain.budget import BudgetLimit, Converter
from rinde.shared.domain.money import Currency, Money
from rinde.shared.domain.rate_type import RateType


def ars(amount: str) -> Money:
    return Money(Decimal(amount), Currency.ARS)


def usd(amount: str) -> Money:
    return Money(Decimal(amount), Currency.USD)


def btc(amount: str) -> Money:
    return Money(Decimal(amount), Currency.BTC)


class TableConverter:
    """Pesos por dólar con compra y venta fijas, salvo los días que no tienen cotización."""

    def __init__(
        self,
        target: Currency = Currency.ARS,
        *,
        buy: str = "1000",
        sell: str = "1100",
        missing: frozenset[date] = frozenset(),
    ) -> None:
        self._target = target
        self._buy = Decimal(buy)
        self._sell = Decimal(sell)
        self._missing = missing
        self.days: list[date] = []

    @property
    def target(self) -> Currency:
        return self._target

    def to_target(self, money: Money, day: date) -> Decimal | None:
        if money.currency is self._target:
            return money.amount
        if money.currency not in {Currency.ARS, Currency.USD}:
            return None
        self.days.append(day)
        if day in self._missing:
            return None
        asset = not money.is_negative
        if money.currency is Currency.USD:
            return money.amount * (self._buy if asset else self._sell)
        return money.amount / (self._sell if asset else self._buy)


class InMemoryBudgetRepository:
    def __init__(self) -> None:
        self.rows: list[BudgetLimit] = []

    async def add(self, limit: BudgetLimit) -> None:
        self.rows.append(limit)

    async def history(self, owner_id: UUID, until: date) -> list[BudgetLimit]:
        return [row for row in self.rows if row.owner_id == owner_id and row.since <= until]


class FixedCategories:
    def __init__(self, owner_id: UUID, *categories: CategoryInfo) -> None:
        self._owner_id = owner_id
        self.items = list(categories)

    async def categories(self, owner_id: UUID) -> list[CategoryInfo]:
        return list(self.items) if owner_id == self._owner_id else []


class FixedSpending:
    def __init__(self, owner_id: UUID, *expenses: CategoryExpense) -> None:
        self._owner_id = owner_id
        self._expenses = list(expenses)
        self.calls: list[tuple[UUID, date, date]] = []

    async def expenses(self, owner_id: UUID, since: date, until: date) -> list[CategoryExpense]:
        self.calls.append((owner_id, since, until))
        if owner_id != self._owner_id:
            return []
        return [item for item in self._expenses if since <= item.day <= until]


class FixedRateType:
    def __init__(self, rate_type: RateType = RateType.MEP) -> None:
        self._rate_type = rate_type

    async def rate_type(self, owner_id: UUID) -> RateType:
        return self._rate_type


class FakeConverterFactory:
    def __init__(self, **converters: TableConverter) -> None:
        self._converters = {Currency(code): converter for code, converter in converters.items()}
        self.calls: list[tuple[Currency, RateType, date, date]] = []

    async def converter(
        self, target: Currency, rate_type: RateType, since: date, until: date
    ) -> Converter:
        self.calls.append((target, rate_type, since, until))
        return self._converters.get(target) or TableConverter(target)
