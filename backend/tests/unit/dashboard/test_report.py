"""Las cuentas del dashboard, sin base ni red (ADR-0018)."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rinde.dashboard.domain.errors import DashboardConstantPricesArsOnlyError
from rinde.dashboard.domain.period import Period
from rinde.dashboard.domain.report import BalanceChange, build_report
from rinde.shared.domain.money import Currency, Money
from tests.unit.dashboard.fakes import (
    RENT,
    TableConverter,
    ars,
    expense,
    income,
    price_index,
    usd,
)

TODAY = date(2026, 11, 10)
PERIOD = Period.of(date(2026, 9, 1), None, TODAY)
SEPT, OCT, NOV = date(2026, 9, 1), date(2026, 10, 1), date(2026, 11, 1)
CHECKING, SAVINGS, WALLET = uuid4(), uuid4(), uuid4()


def test_spending_by_category_from_most_to_least() -> None:
    flows = [
        expense(date(2026, 9, 3), ars("100.00")),
        expense(date(2026, 10, 3), ars("50.00")),
        expense(date(2026, 10, 1), ars("500.00"), RENT),
        income(date(2026, 10, 1), ars("9000.00")),
    ]

    report = build_report(PERIOD, flows, [], TableConverter())

    assert [(item.category.name, item.total) for item in report.spending] == [
        ("Alquiler", ars("500.00")),
        ("Supermercado", ars("150.00")),
    ]


def test_every_month_shows_up_even_without_movements() -> None:
    flows = [
        income(date(2026, 9, 5), ars("1000.00")),
        expense(date(2026, 9, 6), ars("300.00")),
        expense(date(2026, 11, 2), ars("20.00")),
    ]

    report = build_report(PERIOD, flows, [], TableConverter())

    assert [(m.month, m.income, m.expense, m.net) for m in report.monthly] == [
        (SEPT, ars("1000.00"), ars("300.00"), ars("700.00")),
        (OCT, ars("0.00"), ars("0.00"), ars("0.00")),
        (NOV, ars("0.00"), ars("20.00"), ars("-20.00")),
    ]


def test_dollars_are_converted_on_the_prudent_side() -> None:
    # Compra 1000, venta 1100. Lo que entra vale a la compra; lo que sale, a la venta.
    flows = [
        income(date(2026, 9, 5), usd("10.00")),
        expense(date(2026, 9, 6), usd("1.00")),
    ]

    report = build_report(PERIOD, flows, [], TableConverter())

    september = report.monthly[0]
    assert september.income == ars("10000.00")
    assert september.expense == ars("1100.00")
    assert report.spending[0].total == ars("1100.00")


def test_each_amount_is_converted_with_the_quote_of_its_own_day() -> None:
    converter = TableConverter()
    flows = [expense(date(2026, 9, 6), usd("1.00")), expense(date(2026, 10, 9), usd("1.00"))]

    build_report(PERIOD, flows, [], converter)

    assert converter.days == [date(2026, 9, 6), date(2026, 10, 9)]


def test_conversions_are_added_before_rounding_once() -> None:
    # A 3 pesos por dólar cada peso son 0.333... dólares. Redondeando cada uno
    # quedaría 0.99; sumando primero, 1.00.
    converter = TableConverter(Currency.USD, buy="3", sell="3")
    flows = [expense(date(2026, 9, day), ars("1.00")) for day in (1, 2, 3)]

    report = build_report(PERIOD, flows, [], converter)

    assert report.monthly[0].expense == usd("1.00")


def test_what_cannot_be_converted_is_left_out_and_reported_in_its_currency() -> None:
    btc = Money(Decimal("0.01000000"), Currency.BTC)
    missing = date(2026, 10, 4)
    flows = [
        expense(date(2026, 9, 2), ars("100.00")),
        income(date(2026, 9, 3), btc),
        expense(missing, usd("2.00")),
    ]

    report = build_report(PERIOD, flows, [], TableConverter(missing=frozenset({missing})))

    assert report.monthly[0].income == ars("0.00")
    assert report.monthly[1].expense == ars("0.00")
    assert [(u.currency, u.income, u.expense) for u in report.unconverted] == [
        (Currency.BTC, btc, Money.zero(Currency.BTC)),
        (Currency.USD, usd("0.00"), usd("2.00")),
    ]


def test_net_worth_closes_each_month_and_ends_today() -> None:
    changes = [
        BalanceChange(CHECKING, None, ars("1000.00")),
        BalanceChange(CHECKING, date(2026, 9, 15), ars("500.00")),
        BalanceChange(CHECKING, date(2026, 11, 9), ars("-200.00")),
        BalanceChange(SAVINGS, date(2026, 10, 31), usd("1.00")),
    ]

    report = build_report(PERIOD, [], changes, TableConverter())

    assert [(p.month, p.on, p.total) for p in report.net_worth] == [
        (SEPT, date(2026, 9, 30), ars("1500.00")),
        (OCT, date(2026, 10, 31), ars("2500.00")),
        (NOV, TODAY, ars("2300.00")),
    ]


def test_a_debt_in_dollars_is_valued_at_the_sell_price() -> None:
    changes = [BalanceChange(WALLET, None, usd("-1.00"))]

    report = build_report(PERIOD, [], changes, TableConverter())

    assert report.net_worth[-1].total == ars("-1100.00")


def test_a_closing_without_a_quote_has_no_total_instead_of_a_wrong_one() -> None:
    changes = [
        BalanceChange(CHECKING, None, ars("1000.00")),
        BalanceChange(SAVINGS, None, usd("1.00")),
    ]
    converter = TableConverter(missing=frozenset({date(2026, 10, 31)}))

    report = build_report(PERIOD, [], changes, converter)

    assert [p.total for p in report.net_worth] == [ars("2000.00"), None, ars("2000.00")]


def test_bitcoin_stays_out_of_net_worth_and_its_balance_is_reported_once() -> None:
    btc = Money(Decimal("0.50000000"), Currency.BTC)
    changes = [
        BalanceChange(CHECKING, None, ars("1000.00")),
        BalanceChange(WALLET, None, btc),
    ]

    report = build_report(PERIOD, [], changes, TableConverter())

    assert [p.total for p in report.net_worth] == [ars("1000.00")] * 3
    assert [(u.currency, u.balance) for u in report.unconverted] == [(Currency.BTC, btc)]


def test_an_empty_account_needs_no_quote() -> None:
    changes = [BalanceChange(SAVINGS, None, usd("0.00"))]
    converter = TableConverter(missing=frozenset({date(2026, 9, 30)}))

    report = build_report(PERIOD, [], changes, converter)

    assert report.net_worth[0].total == ars("0.00")
    assert converter.days == []


amounts = st.decimals(min_value=Decimal("0.01"), max_value=Decimal(10**9), places=2)


@given(st.lists(st.tuples(amounts, st.booleans()), max_size=30))
def test_the_net_of_a_month_is_exactly_income_minus_expense(
    items: list[tuple[Decimal, bool]],
) -> None:
    converter = TableConverter(Currency.USD, buy="1234.5", sell="1300.7")
    flows = [
        (income if is_income else expense)(date(2026, 9, 1), ars(str(amount)))
        for amount, is_income in items
    ]

    month = build_report(PERIOD, flows, [], converter).monthly[0]

    assert month.net == month.income - month.expense


def test_constant_prices_bring_each_month_to_the_prices_of_the_base_month() -> None:
    flows = [
        income(date(2026, 9, 5), ars("1000.00")),
        expense(date(2026, 9, 6), ars("300.00")),
        expense(date(2026, 10, 2), ars("110.00")),
    ]
    prices = price_index((OCT, "132"), m2026_09="120", m2026_10="132")

    constant = build_report(PERIOD, flows, [], TableConverter(), prices).constant

    assert constant is not None
    assert constant.base_month == OCT
    # Septiembre por 132 / 120 = 1,1; octubre ya está en sus propios precios.
    assert [(m.month, m.income, m.expense, m.net) for m in constant.monthly] == [
        (SEPT, ars("1100.00"), ars("330.00"), ars("770.00")),
        (OCT, ars("0.00"), ars("110.00"), ars("-110.00")),
        (NOV, None, None, None),
    ]


def test_the_nominal_report_does_not_change_with_constant_prices() -> None:
    flows = [expense(date(2026, 9, 6), ars("300.00"))]
    prices = price_index((OCT, "132"), m2026_09="120", m2026_10="132")

    nominal = build_report(PERIOD, flows, [], TableConverter())
    adjusted = build_report(PERIOD, flows, [], TableConverter(), prices)

    assert adjusted.monthly == nominal.monthly
    assert adjusted.spending == nominal.spending


def test_dollars_are_converted_first_and_adjusted_after() -> None:
    # 1 USD de gasto a 1100 (venta, del lado prudente) son 1100 pesos de septiembre.
    flows = [expense(date(2026, 9, 6), usd("1.00"))]
    prices = price_index((OCT, "150"), m2026_09="100", m2026_10="150")

    constant = build_report(PERIOD, flows, [], TableConverter(), prices).constant

    assert constant is not None
    assert constant.monthly[0].expense == ars("1650.00")


def test_the_adjustment_is_rounded_once_per_month() -> None:
    # Tres gastos de 0,01 por 4/3: cada uno redondeado daría 0,03; la suma, 0,04.
    flows = [expense(date(2026, 9, day), ars("0.01")) for day in (1, 2, 3)]
    prices = price_index((OCT, "4"), m2026_09="3", m2026_10="4")

    constant = build_report(PERIOD, flows, [], TableConverter(), prices).constant

    assert constant is not None
    assert constant.monthly[0].expense == ars("0.04")


def test_without_any_cpi_nothing_is_adjusted() -> None:
    flows = [expense(date(2026, 9, 6), ars("300.00"))]

    constant = build_report(PERIOD, flows, [], TableConverter(), price_index(None)).constant

    assert constant is not None
    assert constant.base_month is None
    assert all(m.income is None and m.net is None for m in constant.monthly)


def test_constant_prices_only_make_sense_in_pesos() -> None:
    with pytest.raises(DashboardConstantPricesArsOnlyError):
        build_report(PERIOD, [], [], TableConverter(Currency.USD), price_index(None))


@given(
    st.lists(st.tuples(amounts, st.booleans()), max_size=30),
    st.decimals(min_value=Decimal(100), max_value=Decimal(99999), places=4),
)
def test_the_adjusted_net_is_exactly_income_minus_expense(
    items: list[tuple[Decimal, bool]], index: Decimal
) -> None:
    flows = [
        (income if is_income else expense)(date(2026, 9, 1), ars(str(amount)))
        for amount, is_income in items
    ]
    prices = price_index((OCT, "12785.9321"), m2026_09=str(index))

    constant = build_report(PERIOD, flows, [], TableConverter(), prices).constant

    assert constant is not None
    month = constant.monthly[0]
    assert month.income is not None
    assert month.expense is not None
    assert month.net == month.income - month.expense
