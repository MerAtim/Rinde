"""El período del dashboard: meses enteros, con el mes en curso hasta hoy."""

from datetime import date

import pytest

from rinde.dashboard.domain.errors import DashboardPeriodInvalidError
from rinde.dashboard.domain.period import MAX_MONTHS, Period

TODAY = date(2026, 11, 10)


def test_without_choosing_it_is_the_last_six_months_up_to_today() -> None:
    period = Period.of(None, None, TODAY)

    assert period.months == [date(2026, month, 1) for month in range(6, 12)]
    assert period.since == date(2026, 6, 1)
    assert period.until == TODAY


def test_a_past_month_closes_on_its_last_day() -> None:
    period = Period.of(date(2026, 1, 1), date(2026, 2, 1), TODAY)

    assert period.until == date(2026, 2, 28)
    assert [period.closing(m) for m in period.months] == [date(2026, 1, 31), date(2026, 2, 28)]


def test_only_the_last_month_moves_the_first_back_across_years() -> None:
    period = Period.of(None, date(2026, 3, 1), TODAY)

    assert period.first == date(2025, 10, 1)


def test_any_day_of_a_month_means_that_month() -> None:
    assert Period.of(date(2026, 4, 17), date(2026, 4, 30), TODAY).months == [date(2026, 4, 1)]


@pytest.mark.parametrize(
    ("first", "last"),
    [
        (date(2026, 5, 1), date(2026, 4, 1)),
        (date(2026, 11, 1), date(2026, 12, 1)),
        (date(2024, 10, 1), date(2026, 11, 1)),
    ],
)
def test_a_wrong_period_is_rejected(first: date, last: date) -> None:
    with pytest.raises(DashboardPeriodInvalidError):
        Period.of(first, last, TODAY)


def test_the_longest_period_allowed() -> None:
    assert len(Period.of(date(2024, 12, 1), None, TODAY).months) == MAX_MONTHS
