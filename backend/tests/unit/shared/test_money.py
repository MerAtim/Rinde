"""Dinero: propiedades que tienen que valer para cualquier monto, y los casos borde."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rinde.shared.domain.money import (
    AmountTooPreciseError,
    Currency,
    CurrencyMismatchError,
    InvalidAmountError,
    Money,
)


def amounts(currency: Currency) -> st.SearchStrategy[Money]:
    """Montos válidos de una moneda, positivos y negativos, hasta mil millones."""
    return st.decimals(
        min_value=Decimal("-1e9"),
        max_value=Decimal("1e9"),
        places=currency.minor_units,
        allow_nan=False,
        allow_infinity=False,
    ).map(lambda amount: Money(amount, currency))


@given(a=amounts(Currency.ARS), b=amounts(Currency.ARS))
def test_addition_is_commutative(a: Money, b: Money) -> None:
    assert a + b == b + a


@given(a=amounts(Currency.USD), b=amounts(Currency.USD), c=amounts(Currency.USD))
def test_addition_is_associative(a: Money, b: Money, c: Money) -> None:
    assert (a + b) + c == a + (b + c)


@given(a=amounts(Currency.BTC))
def test_zero_is_neutral_and_subtracting_itself_gives_zero(a: Money) -> None:
    zero = Money.zero(Currency.BTC)
    assert a + zero == a
    assert (a - a).is_zero
    negated = -a
    assert -negated == a


@given(items=st.lists(amounts(Currency.ARS), max_size=50))
def test_total_matches_adding_one_by_one(items: list[Money]) -> None:
    expected = Money.zero(Currency.ARS)
    for item in items:
        expected = expected + item

    assert Money.total(items, Currency.ARS) == expected


@given(a=amounts(Currency.USD), b=amounts(Currency.USD))
def test_subtraction_never_loses_cents(a: Money, b: Money) -> None:
    assert (a - b) + b == a


def test_the_total_of_nothing_is_zero_in_the_requested_currency() -> None:
    assert Money.total([], Currency.USD) == Money.zero(Currency.USD)


@pytest.mark.parametrize(
    "operation",
    [
        lambda a, b: a + b,
        lambda a, b: a - b,
        lambda a, b: a < b,
        lambda a, b: a >= b,
    ],
)
def test_different_currencies_are_never_mixed(operation: object) -> None:
    pesos = Money(Decimal("1000.00"), Currency.ARS)
    dolares = Money(Decimal("1.00"), Currency.USD)

    with pytest.raises(CurrencyMismatchError):
        operation(pesos, dolares)  # type: ignore[operator]


def test_money_in_different_currencies_is_not_equal() -> None:
    assert Money(Decimal(1), Currency.ARS) != Money(Decimal(1), Currency.USD)


@pytest.mark.parametrize("amount", [0.1, 1, True, "10.00", None])
def test_only_decimal_amounts_are_accepted(amount: object) -> None:
    with pytest.raises(InvalidAmountError):
        Money(amount, Currency.ARS)  # type: ignore[arg-type]


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_amounts_are_rejected(amount: str) -> None:
    with pytest.raises(InvalidAmountError):
        Money(Decimal(amount), Currency.ARS)


def test_an_amount_too_large_for_decimal_arithmetic_is_rejected() -> None:
    with pytest.raises(InvalidAmountError):
        Money(Decimal("1e40"), Currency.ARS)


@pytest.mark.parametrize(
    ("amount", "currency"),
    [("10.005", Currency.ARS), ("0.001", Currency.USD), ("0.000000001", Currency.BTC)],
)
def test_extra_precision_is_an_error_and_not_a_silent_rounding(
    amount: str, currency: Currency
) -> None:
    with pytest.raises(AmountTooPreciseError):
        Money(Decimal(amount), currency)


def test_bitcoin_keeps_its_eight_decimals() -> None:
    assert Money(Decimal("0.00000001"), Currency.BTC).amount == Decimal("0.00000001")


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("0.125", "0.12"),  # el medio va al par: 2
        ("0.135", "0.14"),  # el medio va al par: 4
        ("0.126", "0.13"),
        ("-0.125", "-0.12"),
    ],
)
def test_rounding_is_explicit_and_goes_half_to_even(amount: str, expected: str) -> None:
    assert Money.rounded(Decimal(amount), Currency.ARS).amount == Decimal(expected)


def test_the_same_value_is_stored_the_same_way() -> None:
    uno = Money(Decimal(1), Currency.ARS)
    uno_con_centavos = Money(Decimal("1.00"), Currency.ARS)

    assert uno == uno_con_centavos
    assert str(uno.amount) == str(uno_con_centavos.amount) == "1.00"
    assert hash(uno) == hash(uno_con_centavos)


def test_negative_zero_is_just_zero() -> None:
    assert str(Money(Decimal("-0.00"), Currency.ARS).amount) == "0.00"


def test_sign_helpers() -> None:
    assert Money(Decimal("-5.00"), Currency.ARS).is_negative
    assert Money(Decimal("5.00"), Currency.ARS).is_positive
    assert Money.zero(Currency.ARS).is_zero
