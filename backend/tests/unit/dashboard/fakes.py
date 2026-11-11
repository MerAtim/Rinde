"""Piezas en memoria para probar el dashboard sin otros módulos."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from rinde.dashboard.application.ports import Ledger, Reference
from rinde.dashboard.domain.report import BalanceChange, CategoryRef, Converter, Flow, FlowKind
from rinde.shared.domain.money import Currency, Money
from rinde.shared.domain.rate_type import RateType

FOOD = CategoryRef(uuid4(), "Supermercado", "groceries")
RENT = CategoryRef(uuid4(), "Alquiler", "rent")
SALARY = CategoryRef(uuid4(), "Sueldo", "salary")


def ars(amount: str) -> Money:
    return Money(Decimal(amount), Currency.ARS)


def usd(amount: str) -> Money:
    return Money(Decimal(amount), Currency.USD)


def expense(day: date, money: Money, category: CategoryRef = FOOD) -> Flow:
    return Flow(day, FlowKind.EXPENSE, category, money)


def income(day: date, money: Money, category: CategoryRef = SALARY) -> Flow:
    return Flow(day, FlowKind.INCOME, category, money)


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

    def supports(self, currency: Currency) -> bool:
        return currency in {Currency.ARS, Currency.USD}

    def to_target(self, money: Money, day: date) -> Decimal | None:
        if money.currency is self._target:
            return money.amount
        if not self.supports(money.currency):
            return None
        self.days.append(day)
        if day in self._missing:
            return None
        asset = not money.is_negative
        if money.currency is Currency.USD:
            return money.amount * (self._buy if asset else self._sell)
        return money.amount / (self._sell if asset else self._buy)


class FakeLedger:
    def __init__(self, flows: list[Flow], changes: list[BalanceChange]) -> None:
        self._ledger = Ledger(flows, changes)
        self.calls: list[tuple[UUID, date, date, frozenset[UUID] | None, Currency]] = []

    async def ledger(
        self,
        owner_id: UUID,
        since: date,
        until: date,
        account_ids: frozenset[UUID] | None,
        reference: Currency,
    ) -> Ledger:
        self.calls.append((owner_id, since, until, account_ids, reference))
        return self._ledger


class FixedReferences:
    def __init__(
        self, currency: Currency = Currency.ARS, rate_type: RateType = RateType.MEP
    ) -> None:
        self._reference = Reference(currency, rate_type)

    async def reference(self, owner_id: UUID) -> Reference:
        return self._reference


class FakeConverters:
    def __init__(self, converter: Converter) -> None:
        self._converter = converter
        self.calls: list[tuple[Currency, RateType, date, date]] = []

    async def converter(
        self, target: Currency, rate_type: RateType, since: date, until: date
    ) -> Converter:
        self.calls.append((target, rate_type, since, until))
        return self._converter
