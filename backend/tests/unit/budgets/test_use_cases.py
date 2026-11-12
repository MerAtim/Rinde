"""Casos de uso de presupuestos con los otros módulos en memoria (ADR-0021)."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from rinde.budgets.application.ports import CategoryExpense, CategoryInfo
from rinde.budgets.application.use_cases import (
    BudgetMonth,
    BudgetsDependencies,
    GetBudgets,
    RemoveBudget,
    SetBudget,
)
from rinde.budgets.domain.budget import BudgetStatus
from rinde.budgets.domain.errors import (
    BudgetAmountInvalidError,
    BudgetCategoryNotExpenseError,
    BudgetCategoryNotFoundError,
    BudgetCurrencyNotAllowedError,
    BudgetMonthInvalidError,
    BudgetNotFoundError,
)
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType
from tests.fakes import FakeClock, FakeTransaction
from tests.unit.budgets.fakes import (
    FakeConverterFactory,
    FixedCategories,
    FixedRateType,
    FixedSpending,
    InMemoryBudgetRepository,
    TableConverter,
    ars,
    btc,
    usd,
)

pytestmark = pytest.mark.anyio

OWNER = uuid4()
STRANGER = uuid4()
FOOD = CategoryInfo(uuid4(), "Supermercado", "supermercado", is_expense=True)
RENT = CategoryInfo(uuid4(), "Alquiler", "alquiler", is_expense=True)
SALARY = CategoryInfo(uuid4(), "Sueldo", "sueldo", is_expense=False)
# Las 12 de Buenos Aires del 10 de noviembre de 2026.
NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)
OCTOBER = date(2026, 10, 1)
NOVEMBER = date(2026, 11, 1)


class World:
    def __init__(self, *expenses: CategoryExpense, **converters: TableConverter) -> None:
        self.budgets = InMemoryBudgetRepository()
        self.transaction = FakeTransaction()
        self.clock = FakeClock()
        self.clock.current = NOW
        self.spending = FixedSpending(OWNER, *expenses)
        self.converters = FakeConverterFactory(**converters)
        self.deps = BudgetsDependencies(
            budgets=self.budgets,
            transaction=self.transaction,
            categories=FixedCategories(OWNER, FOOD, RENT, SALARY),
            spending=self.spending,
            rate_types=FixedRateType(RateType.BLUE),
            converters=self.converters,
            clock=self.clock,
        )

    async def set(self, category: UUID, amount: str, currency: str = "ARS") -> None:
        money = usd(amount) if currency == "USD" else ars(amount)
        await SetBudget(self.deps).execute(OWNER, category, money)

    async def get(self, month: date | None = None, owner: UUID = OWNER) -> BudgetMonth:
        return await GetBudgets(self.deps).execute(owner, month)


def _expense(
    category: CategoryInfo, day: int, amount: str, currency: str = "ARS"
) -> CategoryExpense:
    money = {"ARS": ars, "USD": usd, "BTC": btc}[currency](amount)
    return CategoryExpense(category.id, date(2026, 11, day), money)


class TestSetBudget:
    async def test_starts_in_the_current_argentine_month(self) -> None:
        world = World()
        # Las 23 del 31 de octubre en Buenos Aires ya son el 1 de noviembre en UTC.
        world.clock.current = datetime(2026, 11, 1, 2, tzinfo=UTC)

        await world.set(FOOD.id, "300000.00")

        assert world.budgets.rows[0].since == OCTOBER
        assert world.transaction.commits == 1

    async def test_the_same_limit_twice_adds_nothing(self) -> None:
        world = World()

        await world.set(FOOD.id, "300000.00")
        await world.set(FOOD.id, "300000.00")

        assert len(world.budgets.rows) == 1
        assert world.transaction.commits == 1

    async def test_a_change_adds_a_vigency_and_keeps_the_month_before(self) -> None:
        world = World()
        world.clock.current = NOW - timedelta(days=31)
        await world.set(FOOD.id, "300000.00")
        world.clock.current = NOW

        await world.set(FOOD.id, "350000.00")

        assert [row.since for row in world.budgets.rows] == [OCTOBER, NOVEMBER]
        assert (await world.get(OCTOBER)).items[0].progress.limit == ars("300000.00")
        assert (await world.get()).items[0].progress.limit == ars("350000.00")

    async def test_a_limit_can_be_in_dollars(self) -> None:
        world = World()

        await world.set(RENT.id, "500.00", "USD")

        assert (await world.get()).items[0].progress.limit == usd("500.00")

    async def test_an_income_category_is_not_budgeted(self) -> None:
        with pytest.raises(BudgetCategoryNotExpenseError):
            await World().set(SALARY.id, "1000.00")

    async def test_someone_elses_category_is_as_if_it_did_not_exist(self) -> None:
        world = World()

        with pytest.raises(BudgetCategoryNotFoundError):
            await SetBudget(world.deps).execute(STRANGER, FOOD.id, ars("1000.00"))
        assert world.budgets.rows == []

    async def test_rejects_a_limit_of_zero(self) -> None:
        with pytest.raises(BudgetAmountInvalidError):
            await World().set(FOOD.id, "0.00")

    async def test_rejects_bitcoin(self) -> None:
        world = World()

        with pytest.raises(BudgetCurrencyNotAllowedError):
            await SetBudget(world.deps).execute(OWNER, FOOD.id, btc("0.10000000"))


class TestRemoveBudget:
    async def test_removes_from_this_month_on_and_keeps_the_past(self) -> None:
        world = World()
        world.clock.current = NOW - timedelta(days=31)
        await world.set(FOOD.id, "300000.00")
        world.clock.current = NOW

        await RemoveBudget(world.deps).execute(OWNER, FOOD.id)

        assert (await world.get()).items == []
        assert len((await world.get(OCTOBER)).items) == 1

    async def test_without_a_limit_there_is_nothing_to_remove(self) -> None:
        world = World()

        with pytest.raises(BudgetNotFoundError):
            await RemoveBudget(world.deps).execute(OWNER, FOOD.id)

    async def test_removing_twice_fails_the_second_time(self) -> None:
        world = World()
        await world.set(FOOD.id, "300000.00")
        await RemoveBudget(world.deps).execute(OWNER, FOOD.id)

        with pytest.raises(BudgetNotFoundError):
            await RemoveBudget(world.deps).execute(OWNER, FOOD.id)

    async def test_someone_elses_category_is_as_if_it_did_not_exist(self) -> None:
        world = World()
        await world.set(FOOD.id, "300000.00")

        with pytest.raises(BudgetCategoryNotFoundError):
            await RemoveBudget(world.deps).execute(STRANGER, FOOD.id)
        assert len(world.budgets.rows) == 1


class TestGetBudgets:
    async def test_measures_the_month_up_to_today(self) -> None:
        world = World(
            _expense(FOOD, 3, "200000.00"),
            _expense(FOOD, 9, "45000.00"),
            _expense(RENT, 5, "1.00"),
        )
        await world.set(FOOD.id, "300000.00")

        result = await world.get()

        assert result.month == NOVEMBER
        assert result.rate_type is RateType.BLUE
        assert world.spending.calls == [(OWNER, NOVEMBER, date(2026, 11, 10))]
        [item] = result.items
        assert item.category == FOOD
        assert item.since == NOVEMBER
        assert item.progress.spent == ars("245000.00")
        assert item.progress.status is BudgetStatus.WARNING

    async def test_a_past_month_is_measured_to_its_last_day(self) -> None:
        world = World()
        world.clock.current = NOW - timedelta(days=31)
        await world.set(FOOD.id, "300000.00")
        world.clock.current = NOW

        await world.get(date(2026, 10, 15))

        assert world.spending.calls == [(OWNER, OCTOBER, date(2026, 10, 31))]

    async def test_a_month_that_has_not_started_has_nothing_to_measure(self) -> None:
        with pytest.raises(BudgetMonthInvalidError):
            await World().get(date(2026, 12, 1))

    async def test_without_budgets_nothing_is_read_from_the_other_modules(self) -> None:
        world = World()

        result = await world.get()

        assert result.items == []
        assert world.spending.calls == []

    async def test_only_fetches_rates_for_convertible_currencies_it_needs(self) -> None:
        world = World(
            _expense(FOOD, 3, "100.00", "USD"),
            _expense(RENT, 4, "0.01000000", "BTC"),
        )
        await world.set(FOOD.id, "300000.00")
        await world.set(RENT.id, "500.00", "USD")

        result = await world.get()

        # Bitcoin no tiene cotización: no se sale a buscar un dólar para él.
        assert world.converters.calls == [
            (Currency.ARS, RateType.BLUE, NOVEMBER, date(2026, 11, 10))
        ]
        rent, food = result.items
        assert food.progress.spent == ars("110000.00")
        assert rent.progress.unconverted == [btc("0.01000000")]

    async def test_someone_else_sees_nothing(self) -> None:
        world = World(_expense(FOOD, 3, "1000.00"))
        await world.set(FOOD.id, "300000.00")

        assert (await world.get(owner=STRANGER)).items == []

    async def test_a_deleted_category_does_not_show_its_orphan_limit(self) -> None:
        world = World()
        await world.set(FOOD.id, "300000.00")
        categories = world.deps.categories
        assert isinstance(categories, FixedCategories)
        categories.items = [RENT, SALARY]

        assert (await world.get()).items == []

    async def test_sorted_by_category_name(self) -> None:
        world = World()
        await world.set(FOOD.id, "300000.00")
        await world.set(RENT.id, "500.00", "USD")

        names = [item.category.name for item in (await world.get()).items]

        assert names == ["Alquiler", "Supermercado"]
