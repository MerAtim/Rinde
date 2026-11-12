"""Reglas del presupuesto: vigencias, medición y redondeo (ADR-0021)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rinde.budgets.domain.budget import (
    BudgetLimit,
    BudgetProgress,
    BudgetStatus,
    Expense,
    latest_in,
    limits_in,
    month_end,
)
from rinde.budgets.domain.errors import (
    BudgetAmountInvalidError,
    BudgetCurrencyNotAllowedError,
    BudgetMonthInvalidError,
)
from rinde.shared.domain.money import Currency, Money
from tests.unit.budgets.fakes import TableConverter, ars, btc, usd

OWNER = uuid4()
FOOD = uuid4()
RENT = uuid4()
AT = datetime(2026, 11, 10, 15, tzinfo=UTC)
SEPTEMBER = date(2026, 9, 1)
OCTOBER = date(2026, 10, 1)
NOVEMBER = date(2026, 11, 1)


def _limit(category: UUID, since: date, limit: Money | None, at: datetime = AT) -> BudgetLimit:
    return BudgetLimit(uuid4(), OWNER, category, since, limit, at)


class TestBudgetLimit:
    def test_starts_on_the_first_day_of_a_month(self) -> None:
        with pytest.raises(BudgetMonthInvalidError):
            _limit(FOOD, date(2026, 11, 2), ars("1000.00"))

    @pytest.mark.parametrize("amount", ["0.00", "-1.00"])
    def test_a_limit_of_zero_or_less_measures_nothing(self, amount: str) -> None:
        with pytest.raises(BudgetAmountInvalidError):
            _limit(FOOD, NOVEMBER, ars(amount))

    def test_bitcoin_cannot_be_the_currency_of_a_limit(self) -> None:
        with pytest.raises(BudgetCurrencyNotAllowedError):
            _limit(FOOD, NOVEMBER, btc("0.01000000"))

    def test_removing_a_limit_has_no_amount(self) -> None:
        assert _limit(FOOD, NOVEMBER, None).limit is None


def _amounts(history: list[BudgetLimit], month: date) -> dict[UUID, Money | None]:
    return {category: item.limit for category, item in limits_in(history, month).items()}


class TestLimitsIn:
    def test_a_limit_repeats_every_month_after_it_starts(self) -> None:
        history = [_limit(FOOD, SEPTEMBER, ars("300000.00"))]

        assert _amounts(history, NOVEMBER) == {FOOD: ars("300000.00")}
        assert _amounts(history, date(2026, 8, 1)) == {}

    def test_a_change_does_not_rewrite_the_months_before_it(self) -> None:
        history = [
            _limit(FOOD, SEPTEMBER, ars("300000.00")),
            _limit(FOOD, NOVEMBER, ars("350000.00")),
        ]

        assert _amounts(history, OCTOBER) == {FOOD: ars("300000.00")}
        assert _amounts(history, NOVEMBER) == {FOOD: ars("350000.00")}

    def test_two_changes_in_the_same_month_keep_the_last_one(self) -> None:
        history = [
            _limit(FOOD, NOVEMBER, ars("400000.00"), AT + timedelta(hours=1)),
            _limit(FOOD, NOVEMBER, ars("350000.00"), AT),
        ]

        assert _amounts(history, NOVEMBER) == {FOOD: ars("400000.00")}

    def test_removing_hides_the_category_from_that_month_on(self) -> None:
        history = [
            _limit(FOOD, SEPTEMBER, ars("300000.00")),
            _limit(RENT, SEPTEMBER, usd("500.00")),
            _limit(FOOD, NOVEMBER, None),
        ]

        assert _amounts(history, OCTOBER) == {FOOD: ars("300000.00"), RENT: usd("500.00")}
        assert _amounts(history, NOVEMBER) == {RENT: usd("500.00")}
        assert latest_in(history, NOVEMBER)[FOOD].limit is None


class TestMeasure:
    def test_measures_against_the_limit_from_zero(self) -> None:
        progress = BudgetProgress.measure(
            ars("100000.00"),
            [
                Expense(date(2026, 11, 3), ars("30000.00")),
                Expense(date(2026, 11, 5), ars("21234.50")),
            ],
            None,
        )

        assert progress.spent == ars("51234.50")
        assert progress.remaining == ars("48765.50")
        assert progress.ratio == Decimal("0.5123")
        assert progress.status is BudgetStatus.ON_TRACK
        assert progress.unconverted == []

    @pytest.mark.parametrize(
        ("spent", "status"),
        [
            ("79999.99", BudgetStatus.ON_TRACK),
            ("80000.00", BudgetStatus.WARNING),
            ("99999.99", BudgetStatus.WARNING),
            ("100000.00", BudgetStatus.OVER),
            ("120000.00", BudgetStatus.OVER),
        ],
    )
    def test_warns_from_80_percent_and_is_over_from_the_limit(
        self, spent: str, status: BudgetStatus
    ) -> None:
        progress = BudgetProgress.measure(
            ars("100000.00"), [Expense(date(2026, 11, 3), ars(spent))], None
        )

        assert progress.status is status

    def test_going_over_leaves_a_negative_remainder(self) -> None:
        progress = BudgetProgress.measure(
            ars("100000.00"), [Expense(date(2026, 11, 3), ars("120000.00"))], None
        )

        assert progress.remaining == ars("-20000.00")
        assert progress.ratio == Decimal("1.2000")

    def test_nothing_spent_is_zero(self) -> None:
        progress = BudgetProgress.measure(usd("500.00"), [], None)

        assert progress.spent == usd("0.00")
        assert progress.ratio == Decimal("0.0000")
        assert progress.status is BudgetStatus.ON_TRACK

    def test_converts_each_expense_with_the_rate_of_its_day_as_a_debt(self) -> None:
        converter = TableConverter(Currency.ARS, buy="1000", sell="1100")

        progress = BudgetProgress.measure(
            ars("300000.00"),
            [Expense(date(2026, 11, 3), usd("100.00")), Expense(date(2026, 11, 4), ars("1000.00"))],
            converter,
        )

        # Lo que se debe, al precio de venta: 100 dólares son 110.000 pesos.
        assert progress.spent == ars("111000.00")
        assert converter.days == [date(2026, 11, 3)]

    def test_what_cannot_be_converted_is_reported_apart_in_its_currency(self) -> None:
        converter = TableConverter(Currency.USD, missing=frozenset({date(2026, 11, 4)}))

        progress = BudgetProgress.measure(
            usd("500.00"),
            [
                Expense(date(2026, 11, 3), btc("0.00100000")),
                Expense(date(2026, 11, 4), ars("5000.00")),
                Expense(date(2026, 11, 5), btc("0.00050000")),
            ],
            converter,
        )

        assert progress.spent == usd("0.00")
        assert progress.unconverted == [ars("5000.00"), btc("0.00150000")]

    def test_without_a_converter_other_currencies_are_left_apart(self) -> None:
        progress = BudgetProgress.measure(
            ars("1000.00"), [Expense(date(2026, 11, 3), usd("1.00"))], None
        )

        assert progress.unconverted == [usd("1.00")]

    def test_rounds_once_at_the_end(self) -> None:
        # Tres gastos de 0,005 pesos: redondeados de a uno darían cero; sumados y
        # redondeados una vez, 0,015 va al par, 0,02 (ROUND_HALF_EVEN).
        converter = TableConverter(Currency.ARS, buy="0.5", sell="0.5")

        progress = BudgetProgress.measure(
            ars("1.00"),
            [Expense(date(2026, 11, day), usd("0.01")) for day in (3, 4, 5)],
            converter,
        )

        assert progress.spent == ars("0.02")

    @given(st.lists(st.integers(min_value=1, max_value=10**9), max_size=20))
    def test_spent_plus_remaining_is_always_the_limit(self, cents: list[int]) -> None:
        limit = ars("150000.00")
        expenses = [
            Expense(date(2026, 11, 3), Money(Decimal(c) / 100, Currency.ARS)) for c in cents
        ]

        progress = BudgetProgress.measure(limit, expenses, None)

        assert progress.spent + progress.remaining == limit


def test_month_end_knows_december_and_leap_years() -> None:
    assert month_end(date(2026, 12, 1)) == date(2026, 12, 31)
    assert month_end(date(2028, 2, 1)) == date(2028, 2, 29)
