"""Repartos por resto mayor: la suma de las partes es siempre el total."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rinde.shared.domain.allocation import AllocationInvalidError, allocate, split_equally
from rinde.shared.domain.money import Currency, Money


def ars(amount: str) -> Money:
    return Money(Decimal(amount), Currency.ARS)


def test_one_hundred_in_three_does_not_lose_a_cent() -> None:
    assert split_equally(ars("100.00"), 3) == [ars("33.34"), ars("33.33"), ars("33.33")]


def test_the_cents_left_go_to_the_largest_remainders() -> None:
    # 10 en 1 / 2 / 3: 1,666... / 3,333... / 5. Sobra un centavo y va al resto más grande.
    parts = allocate(ars("10.00"), [Decimal(1), Decimal(2), Decimal(3)])

    assert parts == [ars("1.67"), ars("3.33"), ars("5.00")]


def test_a_negative_total_keeps_its_sign() -> None:
    assert split_equally(ars("-0.05"), 2) == [ars("-0.03"), ars("-0.02")]


def test_bitcoin_splits_to_the_satoshi() -> None:
    btc = Money(Decimal("0.00000010"), Currency.BTC)

    assert sum((part.amount for part in split_equally(btc, 3)), Decimal(0)) == btc.amount


@pytest.mark.parametrize(
    "weights",
    [[], [Decimal(-1), Decimal(2)], [Decimal(0), Decimal(0)]],
    ids=["sin partes", "peso negativo", "pesos en cero"],
)
def test_an_impossible_allocation(weights: list[Decimal]) -> None:
    with pytest.raises(AllocationInvalidError):
        allocate(ars("1.00"), weights)


def test_zero_equal_parts_is_impossible() -> None:
    with pytest.raises(AllocationInvalidError):
        split_equally(ars("1.00"), 0)


@given(
    st.decimals(min_value=Decimal("-1000000"), max_value=Decimal("1000000"), places=2),
    st.lists(st.integers(min_value=0, max_value=1000), min_size=1, max_size=48).filter(any),
)
def test_the_parts_always_add_up_to_the_total(amount: Decimal, weights: list[int]) -> None:
    total = ars(str(amount))

    parts = allocate(total, [Decimal(weight) for weight in weights])

    assert Money.total(parts, Currency.ARS) == total
    assert len(parts) == len(weights)


@given(
    st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000000"), places=2),
    st.integers(min_value=1, max_value=48),
)
def test_equal_parts_differ_by_one_cent_at_most(amount: Decimal, parts: int) -> None:
    split = split_equally(ars(str(amount)), parts)

    amounts = [part.amount for part in split]
    assert max(amounts) - min(amounts) <= Decimal("0.01")
    assert amounts == sorted(amounts, reverse=True)
