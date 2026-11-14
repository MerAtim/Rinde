"""El índice de un mes: solo valores posibles, sin redondeo en silencio."""

from datetime import date
from decimal import Decimal

import pytest

from rinde.inflation.domain.cpi import CpiMonth, CpiSource, round_index
from rinde.inflation.domain.errors import CpiMonthInvalidError


def test_a_published_index() -> None:
    month = CpiMonth(date(2026, 10, 1), Decimal("12785.9321"), CpiSource.INDEC)

    assert month.index == Decimal("12785.9321")


@pytest.mark.parametrize(
    "index",
    [
        Decimal(0),
        Decimal(-1),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("1.00001"),
        Decimal(10) ** 10,
    ],
    ids=["cero", "negativo", "NaN", "infinito", "cinco decimales", "no entra en la columna"],
)
def test_an_impossible_index(index: Decimal) -> None:
    with pytest.raises(CpiMonthInvalidError):
        CpiMonth(date(2026, 10, 1), index, CpiSource.INDEC)


def test_a_month_starts_on_its_first_day() -> None:
    with pytest.raises(CpiMonthInvalidError):
        CpiMonth(date(2026, 10, 2), Decimal(1), CpiSource.INDEC)


def test_the_index_is_rounded_only_on_purpose() -> None:
    assert round_index(Decimal("1.00005")) == Decimal("1.0000")
    assert round_index(Decimal("1.00015")) == Decimal("1.0002")


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal(10) ** 30], ids=["NaN", "enorme"])
def test_what_cannot_be_rounded(value: Decimal) -> None:
    with pytest.raises(CpiMonthInvalidError):
        round_index(value)
