"""Respaldo entre fuentes y caché, con fuentes en memoria."""

from datetime import date, timedelta

import pytest

from rinde.rates.application.ports import QuoteRequest, RateSourceUnavailableError
from rinde.rates.application.providers import CachedRateProvider, FallbackRateProvider
from rinde.rates.domain.quote import ALL_RATE_TYPES, Quote, RateSource, RateType
from tests.fakes import FakeClock
from tests.unit.rates.fakes import FakeRateProvider, quote

pytestmark = pytest.mark.anyio

DAY = date(2026, 11, 10)
TODAY = QuoteRequest(DAY, ALL_RATE_TYPES, current=True)
MEP_AND_BLUE = QuoteRequest(DAY, frozenset({RateType.MEP, RateType.BLUE}), current=True)


async def test_the_first_source_that_answers_wins() -> None:
    first = FakeRateProvider(quote(RateType.MEP), quote(RateType.BLUE))
    second = FakeRateProvider(quote(RateType.MEP, source=RateSource.ARGENTINADATOS))

    result = await FallbackRateProvider([("a", first), ("b", second)]).quotes(MEP_AND_BLUE)

    assert {q.source for q in result.values()} == {RateSource.DOLARAPI}
    assert second.requests == []


async def test_a_source_that_is_down_is_skipped() -> None:
    down = FakeRateProvider(down=True)
    backup = FakeRateProvider(quote(RateType.BLUE, source=RateSource.CRIPTOYA))

    result = await FallbackRateProvider([("a", down), ("b", backup)]).quotes(MEP_AND_BLUE)

    assert result == {RateType.BLUE: quote(RateType.BLUE, source=RateSource.CRIPTOYA)}


async def test_each_source_is_only_asked_for_what_the_previous_ones_did_not_have() -> None:
    """CriptoYa no publica el MEP: si DolarAPI lo tiene, a CriptoYa solo se le pide el blue."""
    first = FakeRateProvider(quote(RateType.MEP))
    second = FakeRateProvider(quote(RateType.BLUE, source=RateSource.CRIPTOYA))

    result = await FallbackRateProvider([("a", first), ("b", second)]).quotes(MEP_AND_BLUE)

    assert result.keys() == {RateType.MEP, RateType.BLUE}
    assert second.requests[0].types == {RateType.BLUE}


async def test_a_source_cannot_slip_in_another_day_or_another_type() -> None:
    class Liar:
        async def quotes(self, request: QuoteRequest) -> dict[RateType, Quote]:
            return {
                RateType.MEP: quote(RateType.MEP, date(2026, 11, 9)),
                RateType.BLUE: quote(RateType.CCL),
            }

    result = await FallbackRateProvider([("liar", Liar())]).quotes(MEP_AND_BLUE)

    assert result == {}


async def test_when_every_source_is_down_the_chain_is_down() -> None:
    chain = FallbackRateProvider([("a", FakeRateProvider(down=True))])

    with pytest.raises(RateSourceUnavailableError):
        await chain.quotes(TODAY)


async def test_a_source_that_answers_empty_is_not_down() -> None:
    assert await FallbackRateProvider([("a", FakeRateProvider())]).quotes(TODAY) == {}


async def test_the_cache_asks_the_sources_once_per_period() -> None:
    clock = FakeClock()
    source = FakeRateProvider(quote(RateType.MEP))
    cache = CachedRateProvider(source, clock, ttl=timedelta(minutes=15))

    first = await cache.quotes(MEP_AND_BLUE)
    clock.advance(timedelta(minutes=14))
    second = await cache.quotes(MEP_AND_BLUE)
    clock.advance(timedelta(minutes=2))
    await cache.quotes(MEP_AND_BLUE)

    assert first == second == {RateType.MEP: quote(RateType.MEP)}
    assert len(source.requests) == 2


async def test_the_cache_only_asks_for_the_types_it_does_not_have() -> None:
    source = FakeRateProvider(quote(RateType.MEP), quote(RateType.BLUE))
    cache = CachedRateProvider(source, FakeClock(), ttl=timedelta(minutes=15))

    await cache.quotes(QuoteRequest(DAY, frozenset({RateType.MEP}), current=True))
    result = await cache.quotes(MEP_AND_BLUE)

    assert result.keys() == {RateType.MEP, RateType.BLUE}
    assert source.requests[1].types == {RateType.BLUE}


async def test_the_cache_remembers_that_a_source_has_no_data() -> None:
    source = FakeRateProvider()
    cache = CachedRateProvider(source, FakeClock(), ttl=timedelta(minutes=15))

    await cache.quotes(MEP_AND_BLUE)
    await cache.quotes(MEP_AND_BLUE)

    assert len(source.requests) == 1


async def test_the_cache_does_not_keep_failures() -> None:
    source = FakeRateProvider(quote(RateType.MEP), down=True)
    cache = CachedRateProvider(source, FakeClock(), ttl=timedelta(minutes=15))

    with pytest.raises(RateSourceUnavailableError):
        await cache.quotes(MEP_AND_BLUE)
    source.down = False

    assert RateType.MEP in await cache.quotes(MEP_AND_BLUE)


async def test_today_and_a_closed_day_are_cached_apart() -> None:
    source = FakeRateProvider(quote(RateType.MEP))
    cache = CachedRateProvider(source, FakeClock(), ttl=timedelta(minutes=15))

    await cache.quotes(MEP_AND_BLUE)
    await cache.quotes(QuoteRequest(DAY, MEP_AND_BLUE.types, current=False))

    assert len(source.requests) == 2


async def test_the_cache_has_a_size_limit() -> None:
    source = FakeRateProvider()
    clock = FakeClock()
    cache = CachedRateProvider(source, clock, ttl=timedelta(minutes=15), max_entries=4)

    for offset in range(10):
        day = DAY - timedelta(days=offset)
        await cache.quotes(QuoteRequest(day, frozenset({RateType.MEP}), current=False))
    await cache.quotes(QuoteRequest(DAY, frozenset({RateType.MEP}), current=False))

    assert len(source.requests) == 11
