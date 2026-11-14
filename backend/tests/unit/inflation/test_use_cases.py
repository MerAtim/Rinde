"""El IPC de un rango: de la base, y de la fuente solo cuando falta algo (ADR-0025)."""

from datetime import UTC, date, datetime

import pytest

from rinde.inflation.application.use_cases import GetCpi, InflationDependencies
from rinde.inflation.domain.errors import CpiRangeInvalidError
from tests.fakes import FakeClock, FakeTransaction
from tests.unit.inflation.fakes import FakeCpiProvider, InMemoryCpi, cpi

pytestmark = pytest.mark.anyio

# Las 12 de Buenos Aires del 14 de noviembre de 2026: octubre ya está publicado.
NOW = datetime(2026, 11, 14, 15, tzinfo=UTC)
AUG, SEPT, OCT, NOV = (date(2026, m, 1) for m in (8, 9, 10, 11))

SERIES = (cpi(AUG, "12276.7660"), cpi(SEPT, "12514.1508"), cpi(OCT, "12785.9321"))


def _get(
    stored: InMemoryCpi, provider: FakeCpiProvider, now: datetime = NOW
) -> tuple[GetCpi, FakeTransaction]:
    clock = FakeClock()
    clock.current = now
    transaction = FakeTransaction()
    deps = InflationDependencies(
        months=stored, provider=provider, transaction=transaction, clock=clock
    )
    return GetCpi(deps), transaction


async def test_with_everything_stored_the_source_is_not_asked() -> None:
    provider = FakeCpiProvider(*SERIES)
    get, _ = _get(InMemoryCpi(*SERIES), provider)

    table = await get.execute(SEPT, date(2026, 11, 14))

    assert provider.calls == 0
    assert list(table.months) == [SEPT, OCT]
    assert table.base == SERIES[-1]


async def test_the_first_time_the_whole_series_is_stored() -> None:
    stored = InMemoryCpi()
    get, transaction = _get(stored, FakeCpiProvider(*SERIES))

    table = await get.execute(OCT, OCT)

    assert list(table.months) == [OCT]
    assert table.base == SERIES[-1]
    assert list(stored.months) == [AUG, SEPT, OCT]
    assert transaction.commits == 1
    assert stored.added[0][1] == NOW


async def test_a_new_month_is_added_without_touching_what_was_stored() -> None:
    old_september = cpi(SEPT, "1.0000")
    stored = InMemoryCpi(cpi(AUG, "12276.7660"), old_september)
    get, _ = _get(stored, FakeCpiProvider(*SERIES))

    table = await get.execute(AUG, OCT)

    assert [m.month for m in stored.added[0][0]] == [OCT]
    assert table.months[SEPT] == old_september
    assert table.base == SERIES[-1]


async def test_before_the_publication_the_source_is_asked_and_nothing_is_made_up() -> None:
    # El 5 de noviembre octubre todavía no salió: la fuente trae hasta septiembre.
    stored = InMemoryCpi(*SERIES[:2])
    provider = FakeCpiProvider(*SERIES[:2])
    get, transaction = _get(stored, provider, datetime(2026, 11, 5, 15, tzinfo=UTC))

    table = await get.execute(SEPT, NOV)

    assert provider.calls == 1
    assert list(table.months) == [SEPT]
    assert table.base == SERIES[1]
    assert transaction.commits == 0


async def test_a_month_in_course_from_the_source_is_not_trusted() -> None:
    stored = InMemoryCpi()
    get, _ = _get(stored, FakeCpiProvider(*SERIES, cpi(NOV, "13000.0000")))

    table = await get.execute(OCT, NOV)

    assert NOV not in stored.months
    assert list(table.months) == [OCT]
    assert table.base == SERIES[-1]


async def test_with_the_source_down_what_is_stored_is_enough() -> None:
    get, transaction = _get(InMemoryCpi(*SERIES[:2]), FakeCpiProvider(down=True))

    table = await get.execute(AUG, OCT)

    assert list(table.months) == [AUG, SEPT]
    assert table.base == SERIES[1]
    assert transaction.commits == 0


async def test_with_nothing_stored_and_the_source_down_there_is_no_base() -> None:
    get, _ = _get(InMemoryCpi(), FakeCpiProvider(down=True))

    table = await get.execute(OCT, OCT)

    assert table.months == {}
    assert table.base is None


async def test_the_days_are_ignored_a_range_is_of_whole_months() -> None:
    get, _ = _get(InMemoryCpi(*SERIES), FakeCpiProvider())

    table = await get.execute(date(2026, 9, 1), date(2026, 10, 31))

    assert list(table.months) == [SEPT, OCT]


async def test_a_range_backwards_is_rejected() -> None:
    get, _ = _get(InMemoryCpi(), FakeCpiProvider())

    with pytest.raises(CpiRangeInvalidError):
        await get.execute(OCT, SEPT)


async def test_an_old_missing_month_does_not_move_the_base() -> None:
    stored = InMemoryCpi(*SERIES[1:])
    get, _ = _get(stored, FakeCpiProvider(*SERIES))

    table = await get.execute(AUG, OCT)

    assert list(table.months) == [AUG, SEPT, OCT]
    assert table.base == SERIES[-1]
