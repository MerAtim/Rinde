"""El calendario compartido: el día argentino y sumar meses."""

from datetime import UTC, date, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rinde.shared.domain.calendar import add_months, argentine_day


def test_at_ten_at_night_in_buenos_aires_it_is_still_the_same_day() -> None:
    assert argentine_day(datetime(2026, 9, 19, 1, tzinfo=UTC)) == date(2026, 9, 18)


def test_a_moment_without_a_time_zone_is_rejected() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        argentine_day(datetime(2026, 9, 19, 1))  # noqa: DTZ001  (es lo que se prueba)


@pytest.mark.parametrize(
    ("day", "months", "expected"),
    [
        (date(2026, 8, 31), 1, date(2026, 9, 30)),
        (date(2027, 1, 31), 1, date(2027, 2, 28)),
        (date(2028, 2, 29), 12, date(2029, 2, 28)),
        (date(2026, 8, 31), 2, date(2026, 10, 31)),
        (date(2026, 11, 14), 2, date(2027, 1, 14)),
        (date(2026, 11, 14), 0, date(2026, 11, 14)),
    ],
    ids=["31 en septiembre", "febrero", "29 de febrero", "vuelve al 31", "cambia de año", "cero"],
)
def test_a_day_the_month_does_not_have_falls_on_its_last_day(
    day: date, months: int, expected: date
) -> None:
    assert add_months(day, months) == expected


@given(st.dates(max_value=date(9000, 12, 31)), st.integers(min_value=0, max_value=1200))
def test_it_lands_on_the_right_month_and_never_after_the_day(day: date, months: int) -> None:
    result = add_months(day, months)

    assert (result.year * 12 + result.month) - (day.year * 12 + day.month) == months
    assert result.day <= day.day
