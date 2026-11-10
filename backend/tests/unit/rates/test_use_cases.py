"""Casos de uso de cotizaciones con fuentes y repositorio en memoria."""

from datetime import UTC, date, datetime

import pytest

from rinde.rates.application.use_cases import GetQuote, GetQuotes, RatesDependencies
from rinde.rates.domain.errors import (
    RateDateInFutureError,
    RateNotFoundError,
    RatesUnavailableError,
)
from rinde.rates.domain.quote import ALL_RATE_TYPES, RateSource, RateType
from tests.fakes import FakeClock, FakeTransaction
from tests.unit.rates.fakes import FakeRateProvider, InMemoryQuotes, quote

pytestmark = pytest.mark.anyio

TODAY = date(2026, 11, 10)
PAST = date(2026, 3, 2)


def _deps(
    provider: FakeRateProvider, quotes: InMemoryQuotes | None = None
) -> tuple[RatesDependencies, FakeTransaction]:
    clock = FakeClock()
    # Las 12 de Buenos Aires del 10 de noviembre.
    clock.current = datetime(2026, 11, 10, 15, tzinfo=UTC)
    transaction = FakeTransaction()
    deps = RatesDependencies(
        quotes=quotes or InMemoryQuotes(),
        provider=provider,
        transaction=transaction,
        clock=clock,
    )
    return deps, transaction


async def test_today_comes_from_the_sources_and_is_not_stored() -> None:
    provider = FakeRateProvider(quote(RateType.BLUE), quote(RateType.MEP))
    quotes = InMemoryQuotes()
    deps, transaction = _deps(provider, quotes)

    result = await GetQuotes(deps).execute()

    assert [q.rate_type for q in result] == [RateType.MEP, RateType.BLUE]
    assert provider.requests[0].current
    assert provider.requests[0].types == ALL_RATE_TYPES
    assert quotes.rows == {}
    assert transaction.commits == 0


async def test_a_closed_day_is_fetched_once_and_then_read_from_the_database() -> None:
    provider = FakeRateProvider(quote(RateType.MEP, PAST, source=RateSource.ARGENTINADATOS))
    quotes = InMemoryQuotes()
    deps, transaction = _deps(provider, quotes)

    first = await GetQuotes(deps).execute(PAST, frozenset({RateType.MEP}))
    provider.down = True
    second = await GetQuotes(deps).execute(PAST, frozenset({RateType.MEP}))

    assert first == second
    assert len(provider.requests) == 1
    assert not provider.requests[0].current
    assert transaction.commits == 1
    assert quotes.fetched_at[(PAST, RateType.MEP, RateSource.ARGENTINADATOS)] == datetime(
        2026, 11, 10, 15, tzinfo=UTC
    )


async def test_only_what_is_missing_from_the_database_is_asked_for() -> None:
    stored = quote(RateType.MEP, PAST, source=RateSource.ARGENTINADATOS)
    provider = FakeRateProvider(quote(RateType.BLUE, PAST, source=RateSource.ARGENTINADATOS))
    deps, _ = _deps(provider, InMemoryQuotes(stored))

    result = await GetQuotes(deps).execute(PAST, frozenset({RateType.MEP, RateType.BLUE}))

    assert [q.rate_type for q in result] == [RateType.MEP, RateType.BLUE]
    assert provider.requests[0].types == {RateType.BLUE}


async def test_what_no_source_has_is_left_out_not_invented() -> None:
    deps, transaction = _deps(FakeRateProvider())

    assert await GetQuotes(deps).execute(PAST) == []
    assert transaction.commits == 0


async def test_with_every_source_down_and_nothing_stored_rates_are_unavailable() -> None:
    deps, _ = _deps(FakeRateProvider(down=True))

    with pytest.raises(RatesUnavailableError):
        await GetQuotes(deps).execute()


async def test_with_every_source_down_what_is_stored_is_still_returned() -> None:
    stored = quote(RateType.MEP, PAST, source=RateSource.ARGENTINADATOS)
    deps, _ = _deps(FakeRateProvider(down=True), InMemoryQuotes(stored))

    assert await GetQuotes(deps).execute(PAST) == [stored]


async def test_a_future_day_has_no_quote() -> None:
    deps, _ = _deps(FakeRateProvider())

    with pytest.raises(RateDateInFutureError):
        await GetQuotes(deps).execute(date(2026, 11, 11))


async def test_the_day_is_the_argentine_one_even_late_at_night() -> None:
    """A las 23 de Buenos Aires ya es el 11 en UTC, pero el 10 sigue siendo hoy."""
    provider = FakeRateProvider(quote(RateType.MEP, TODAY))
    deps, _ = _deps(provider)
    deps.clock.current = datetime(2026, 11, 11, 2, tzinfo=UTC)  # type: ignore[attr-defined]

    result = await GetQuotes(deps).execute()

    assert provider.requests[0].day == TODAY
    assert provider.requests[0].current
    assert len(result) == 1


async def test_one_type_is_returned_or_reported_missing() -> None:
    deps, _ = _deps(FakeRateProvider(quote(RateType.BLUE)))

    assert (await GetQuote(deps).execute(RateType.BLUE)).rate_type is RateType.BLUE
    with pytest.raises(RateNotFoundError):
        await GetQuote(deps).execute(RateType.CCL)
