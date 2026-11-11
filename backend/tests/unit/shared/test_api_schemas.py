"""Cómo sale el dinero en JSON: siempre como string decimal (ADR-0002)."""

from decimal import Decimal

import pytest

from rinde.shared.api.schemas import MoneyResponse, decimal_text
from rinde.shared.domain.money import Currency, Money


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (Decimal("0E-8"), "0.00000000"),
        (Decimal("0.00"), "0.00"),
        (Decimal("1E+3"), "1000"),
        (Decimal("-15300.50"), "-15300.50"),
        (Decimal("0.00000001"), "0.00000001"),
    ],
)
def test_never_in_scientific_notation(value: Decimal, text: str) -> None:
    assert decimal_text(value) == text


def test_a_zero_bitcoin_balance_keeps_its_eight_decimals() -> None:
    zero = Money(Decimal(0).quantize(Currency.BTC.quantum), Currency.BTC)

    assert MoneyResponse.from_money(zero).model_dump(mode="json") == {
        "amount": "0.00000000",
        "currency": "BTC",
    }
