"""Conversión de montos: qué precio se usa y cómo se redondea."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rinde.rates.domain.conversion import convert
from rinde.rates.domain.errors import ConversionNotSupportedError
from rinde.shared.domain.money import Currency, Money
from tests.unit.rates.fakes import quote

# Compra 1560,20 y venta 1587,90.
MEP = quote()


def _money(amount: str, currency: Currency) -> Money:
    return Money(Decimal(amount), currency)


def test_dollars_you_have_are_valued_at_the_buy_price() -> None:
    """Para pasarlos a pesos los venderías: te pagan la compra."""
    result = convert(_money("100.00", Currency.USD), MEP)

    assert result.converted == _money("156020.00", Currency.ARS)
    assert result.rate == MEP.buy
    assert result.quote == MEP


def test_dollars_you_owe_are_valued_at_the_sell_price() -> None:
    """Para cancelarlos tenés que comprarlos: pagás la venta."""
    result = convert(_money("-100.00", Currency.USD), MEP)

    assert result.converted == _money("-158790.00", Currency.ARS)
    assert result.rate == MEP.sell


def test_pesos_you_have_buy_dollars_at_the_sell_price() -> None:
    result = convert(_money("158790.00", Currency.ARS), MEP)

    assert result.converted == _money("100.00", Currency.USD)
    assert result.rate == MEP.sell


def test_pesos_you_owe_are_valued_at_the_buy_price() -> None:
    result = convert(_money("-156020.00", Currency.ARS), MEP)

    assert result.converted == _money("-100.00", Currency.USD)
    assert result.rate == MEP.buy


def test_zero_is_zero_in_the_other_currency() -> None:
    assert convert(Money.zero(Currency.USD), MEP).converted == Money.zero(Currency.ARS)


def test_the_result_is_rounded_once_and_half_even() -> None:
    # 1000 / 1587,90 = 0,62975... y 1 / 1587,90 = 0,000629...: redondea a centavos.
    assert convert(_money("1000.00", Currency.ARS), MEP).converted == _money("0.63", Currency.USD)
    assert convert(_money("1.00", Currency.ARS), MEP).converted == _money("0.00", Currency.USD)
    # Justo en el medio, va al par: 15,605 a 15,60 y 15,615 a 15,62.
    down = quote(buy="1560.5", sell="1587.90")
    up = quote(buy="1561.5", sell="1587.90")
    assert convert(_money("0.01", Currency.USD), down).converted == _money("15.60", Currency.ARS)
    assert convert(_money("0.01", Currency.USD), up).converted == _money("15.62", Currency.ARS)


def test_bitcoin_has_no_rate_against_this_pair() -> None:
    with pytest.raises(ConversionNotSupportedError):
        convert(_money("0.5", Currency.BTC), MEP)


@given(cents=st.integers(min_value=-(10**14), max_value=10**14))
def test_converting_never_overvalues_what_you_have(cents: int) -> None:
    """Ida y vuelta, nunca se termina con más de lo que se tenía: la regla es prudente."""
    dollars = Money(Decimal(cents).scaleb(-2), Currency.USD)

    back = convert(convert(dollars, MEP).converted, MEP).converted

    assert back <= dollars
