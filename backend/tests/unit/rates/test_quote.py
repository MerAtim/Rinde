"""Reglas de una cotización: lo que una fuente no puede hacer pasar por válido."""

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from rinde.rates.domain.errors import QuoteInvalidError
from rinde.rates.domain.quote import (
    ALL_RATE_TYPES,
    Quote,
    RateSource,
    RateType,
    argentine_day,
    round_rate,
)
from rinde.shared.domain.money import Currency

DAY = date(2026, 11, 10)


def _quote(**fields: object) -> Quote:
    values: dict[str, object] = {
        "rate_type": RateType.MEP,
        "day": DAY,
        "buy": Decimal("1560.2"),
        "sell": Decimal("1587.9"),
        "source": RateSource.DOLARAPI,
        **fields,
    }
    return Quote(**values)  # type: ignore[arg-type]


def test_a_quote_keeps_its_values_with_the_column_precision() -> None:
    quote = _quote()

    assert (quote.buy, quote.sell) == (Decimal("1560.20000000"), Decimal("1587.90000000"))
    assert (quote.base, quote.counter) == (Currency.USD, Currency.ARS)


def test_buy_and_sell_can_be_equal() -> None:
    """Algunas fuentes publican un solo valor, como el dólar tarjeta."""
    quote = _quote(buy=Decimal(2041), sell=Decimal(2041))

    assert quote.buy == quote.sell


@pytest.mark.parametrize(
    "fields",
    [
        {"buy": Decimal(0)},
        {"buy": Decimal(-1)},
        {"sell": Decimal("NaN")},
        {"sell": Decimal("Infinity")},
        {"buy": 1560.2},
        {"buy": Decimal("1600"), "sell": Decimal("1500")},
        {"buy": Decimal("1.123456789")},
        {"sell": Decimal(10) ** 16},
        {"day": datetime(2026, 11, 10, tzinfo=UTC)},
        {"updated_at": datetime(2026, 11, 10, 12)},  # noqa: DTZ001  (sin zona a propósito)
        {"base": Currency.ARS},
    ],
)
def test_an_impossible_quote_cannot_exist(fields: dict[str, object]) -> None:
    with pytest.raises(QuoteInvalidError):
        _quote(**fields)


def test_rounding_at_the_edge_is_explicit_and_half_even() -> None:
    assert round_rate(Decimal("1665.2290000005")) == Decimal("1665.22900000")
    assert round_rate(Decimal("1.000000005")) == Decimal("1.00000000")
    assert round_rate(Decimal("1.000000015")) == Decimal("1.00000002")


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("1e40")])
def test_rounding_rejects_what_does_not_fit(value: Decimal) -> None:
    with pytest.raises(QuoteInvalidError):
        round_rate(value)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (datetime(2026, 11, 10, 12, tzinfo=UTC), date(2026, 11, 10)),
        # 01:30 UTC del 11 todavía son las 22:30 del 10 en Buenos Aires.
        (datetime(2026, 11, 11, 1, 30, tzinfo=UTC), date(2026, 11, 10)),
        (datetime(2026, 11, 11, 3, tzinfo=UTC), date(2026, 11, 11)),
        (datetime(2026, 11, 10, 23, tzinfo=timezone(timedelta(hours=-3))), date(2026, 11, 10)),
    ],
)
def test_the_day_is_the_argentine_one(moment: datetime, expected: date) -> None:
    assert argentine_day(moment) == expected


def test_a_moment_without_time_zone_has_no_day() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        argentine_day(datetime(2026, 11, 10, 12))  # noqa: DTZ001


def test_there_are_six_dollars() -> None:
    assert {t.value for t in ALL_RATE_TYPES} == {"official", "mep", "ccl", "blue", "card", "crypto"}
