"""El caso de uso del dashboard, con los otros módulos en memoria."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from rinde.dashboard.application.use_cases import DashboardDependencies, GetDashboard
from rinde.dashboard.domain.errors import DashboardPeriodInvalidError
from rinde.dashboard.domain.report import BalanceChange, Flow
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType
from tests.fakes import FakeClock
from tests.unit.dashboard.fakes import (
    FakeConverters,
    FakeLedger,
    FixedReferences,
    TableConverter,
    ars,
    expense,
    usd,
)

pytestmark = pytest.mark.anyio

OWNER = uuid4()


def _dashboard(
    flows: list[Flow],
    changes: list[BalanceChange] | None = None,
    *,
    currency: Currency = Currency.ARS,
    rate_type: RateType = RateType.MEP,
) -> tuple[GetDashboard, FakeLedger, FakeConverters]:
    clock = FakeClock()
    # 23 del 30 de noviembre en Buenos Aires: en UTC ya es diciembre.
    clock.current = datetime(2026, 12, 1, 2, tzinfo=UTC)
    ledger = FakeLedger(flows, changes or [])
    converters = FakeConverters(TableConverter(currency))
    deps = DashboardDependencies(
        ledger=ledger,
        references=FixedReferences(currency, rate_type),
        converters=converters,
        clock=clock,
    )
    return GetDashboard(deps), ledger, converters


async def test_the_period_follows_the_argentine_calendar() -> None:
    dashboard, ledger, _ = _dashboard([])

    result = await dashboard.execute(OWNER)

    assert result.period.last == date(2026, 11, 1)
    assert ledger.calls == [(OWNER, date(2026, 6, 1), date(2026, 11, 30), None, Currency.ARS)]


async def test_with_everything_in_the_reference_currency_no_quote_is_fetched() -> None:
    dashboard, _, converters = _dashboard([expense(date(2026, 11, 2), ars("10.00"))])

    result = await dashboard.execute(OWNER)

    assert converters.calls == []
    assert result.report.monthly[-1].expense == ars("10.00")


async def test_another_currency_brings_the_chosen_dollar_for_the_whole_period() -> None:
    dashboard, _, converters = _dashboard(
        [expense(date(2026, 11, 2), usd("1.00"))], currency=Currency.ARS, rate_type=RateType.BLUE
    )

    result = await dashboard.execute(OWNER, first=date(2026, 10, 1))

    assert converters.calls == [
        (Currency.ARS, RateType.BLUE, date(2026, 10, 1), date(2026, 11, 30))
    ]
    assert result.reference.rate_type is RateType.BLUE


async def test_a_balance_in_another_currency_also_needs_quotes() -> None:
    dashboard, _, converters = _dashboard(
        [], [BalanceChange(uuid4(), None, ars("1.00"))], currency=Currency.USD
    )

    await dashboard.execute(OWNER)

    assert len(converters.calls) == 1


async def test_the_chosen_accounts_reach_the_ledger() -> None:
    dashboard, ledger, _ = _dashboard([])
    chosen = frozenset({uuid4()})

    await dashboard.execute(OWNER, account_ids=chosen)

    assert ledger.calls[0][3] == chosen


async def test_a_period_in_the_future_is_rejected_before_reading_anything() -> None:
    dashboard, ledger, _ = _dashboard([])

    with pytest.raises(DashboardPeriodInvalidError):
        await dashboard.execute(OWNER, last=date(2026, 12, 1))

    assert ledger.calls == []
