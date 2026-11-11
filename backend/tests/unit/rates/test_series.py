"""La cotización de cada día de un rango, la serie en caché y el conversor por día (ADR-0018)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from rinde.rates.application.converter import DayConverter, GetConverter
from rinde.rates.application.providers import CachedHistoryProvider
from rinde.rates.application.use_cases import (
    MAX_CARRY_FORWARD,
    GetQuoteSeries,
    RatesDependencies,
)
from rinde.rates.domain.conversion import convert, convert_exact
from rinde.rates.domain.errors import RateDateInFutureError, RateRangeInvalidError
from rinde.rates.domain.quote import Quote, RateSource
from rinde.shared.domain.money import Currency, Money
from rinde.shared.domain.rate_type import RateType
from tests.fakes import FakeClock, FakeTransaction
from tests.unit.rates.fakes import FakeHistoryProvider, FakeRateProvider, InMemoryQuotes, quote

pytestmark = pytest.mark.anyio

# Las 12 de Buenos Aires del 10 de noviembre de 2026.
NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)
TODAY = date(2026, 11, 10)


def _day(month: int, day: int) -> date:
    return date(2026, month, day)


def _past(day: date, buy: str = "1500", sell: str = "1520") -> Quote:
    return quote(RateType.MEP, day, buy=buy, sell=sell, source=RateSource.ARGENTINADATOS)


def _deps(
    *,
    stored: InMemoryQuotes | None = None,
    history: FakeHistoryProvider | None = None,
    provider: FakeRateProvider | None = None,
) -> tuple[RatesDependencies, FakeTransaction]:
    clock = FakeClock()
    clock.current = NOW
    transaction = FakeTransaction()
    deps = RatesDependencies(
        quotes=stored or InMemoryQuotes(),
        provider=provider or FakeRateProvider(),
        history=history or FakeHistoryProvider(),
        transaction=transaction,
        clock=clock,
    )
    return deps, transaction


def _days(since: date, until: date) -> list[date]:
    return [since + timedelta(days=offset) for offset in range((until - since).days + 1)]


async def test_a_stored_range_does_not_ask_any_source() -> None:
    stored = InMemoryQuotes(*(quote(RateType.MEP, d) for d in _days(_day(3, 1), _day(3, 31))))
    history = FakeHistoryProvider(down=True)
    deps, transaction = _deps(stored=stored, history=history)

    series = await GetQuoteSeries(deps).execute(RateType.MEP, _day(3, 1), _day(3, 31))

    assert sorted(series) == _days(_day(3, 1), _day(3, 31))
    assert history.requests == []
    assert transaction.commits == 0


async def test_missing_days_bring_the_series_once_and_store_only_what_was_missing() -> None:
    every_day = _days(_day(2, 20), _day(3, 31))
    history = FakeHistoryProvider(*(quote(RateType.MEP, d, source=RateSource.ARGENTINADATOS)
                                    for d in every_day))  # fmt: skip
    already = quote(RateType.MEP, _day(3, 15), buy="1", sell="2")
    stored = InMemoryQuotes(already)
    deps, transaction = _deps(stored=stored, history=history)

    series = await GetQuoteSeries(deps).execute(RateType.MEP, _day(3, 1), _day(3, 31))
    again = await GetQuoteSeries(deps).execute(RateType.MEP, _day(3, 1), _day(3, 31))

    assert series == again
    assert history.requests == [RateType.MEP]
    assert transaction.commits == 1
    # Una fila guardada no se pisa: el 15 sigue siendo la que estaba.
    assert series[_day(3, 15)] is already
    # Se guardó el rango pedido y los días de antes que sirven para arrastrar.
    stored_days = {day for (day, _, _) in stored.rows}
    assert stored_days == set(_days(_day(3, 1) - MAX_CARRY_FORWARD, _day(3, 31)))


async def test_a_day_without_its_own_quote_takes_the_last_one_before_it() -> None:
    friday = _past(_day(3, 6))
    stored = InMemoryQuotes(friday, _past(_day(3, 9), buy="1510", sell="1530"))
    deps, _ = _deps(stored=stored, history=FakeHistoryProvider(down=True))

    series = await GetQuoteSeries(deps).execute(RateType.MEP, _day(3, 6), _day(3, 9))

    # El sábado y el domingo valen lo del viernes, y lo dicen: la fecha es la del viernes.
    assert series[_day(3, 7)] is friday
    assert series[_day(3, 8)].day == _day(3, 6)
    assert series[_day(3, 9)].buy == Decimal(1510)


async def test_the_last_price_is_not_dragged_beyond_the_limit() -> None:
    old = _past(_day(3, 1))
    deps, _ = _deps(stored=InMemoryQuotes(old), history=FakeHistoryProvider(down=True))

    series = await GetQuoteSeries(deps).execute(RateType.MEP, _day(3, 1), _day(3, 20))

    assert max(series) == _day(3, 1) + MAX_CARRY_FORWARD
    assert _day(3, 20) not in series


async def test_the_first_day_can_take_a_price_from_before_the_range() -> None:
    sunday_before = _past(_day(2, 28))
    deps, _ = _deps(stored=InMemoryQuotes(sunday_before), history=FakeHistoryProvider(down=True))

    series = await GetQuoteSeries(deps).execute(RateType.MEP, _day(3, 1), _day(3, 2))

    assert series[_day(3, 1)] is sunday_before


async def test_with_the_history_source_down_what_is_stored_still_serves() -> None:
    deps, transaction = _deps(
        stored=InMemoryQuotes(_past(_day(3, 2))), history=FakeHistoryProvider(down=True)
    )

    series = await GetQuoteSeries(deps).execute(RateType.MEP, _day(3, 2), _day(3, 31))

    assert _day(3, 2) in series
    assert _day(3, 31) not in series
    assert transaction.commits == 0


async def test_today_comes_live_and_is_not_stored() -> None:
    live = quote(RateType.MEP, TODAY)
    history = FakeHistoryProvider(quote(RateType.MEP, TODAY, buy="1", sell="2"))
    stored = InMemoryQuotes(*(_past(d) for d in _days(_day(11, 1), _day(11, 9))))
    deps, _ = _deps(stored=stored, history=history, provider=FakeRateProvider(live))

    series = await GetQuoteSeries(deps).execute(RateType.MEP, _day(11, 1), TODAY)

    assert series[TODAY] is live
    assert all(day != TODAY for (day, _, _) in stored.rows)
    assert history.requests == []


async def test_without_a_live_quote_today_takes_yesterday() -> None:
    yesterday = _past(_day(11, 9))
    deps, _ = _deps(
        stored=InMemoryQuotes(yesterday),
        history=FakeHistoryProvider(down=True),
        provider=FakeRateProvider(down=True),
    )

    series = await GetQuoteSeries(deps).execute(RateType.MEP, _day(11, 9), TODAY)

    assert series[TODAY] is yesterday


async def test_the_series_of_another_dollar_is_not_mixed_in() -> None:
    history = FakeHistoryProvider(quote(RateType.BLUE, _day(3, 2)))
    deps, _ = _deps(history=history)

    assert await GetQuoteSeries(deps).execute(RateType.MEP, _day(3, 2), _day(3, 2)) == {}


@pytest.mark.parametrize(
    ("since", "until", "error"),
    [
        (_day(3, 2), _day(3, 1), RateRangeInvalidError),
        (date(2024, 1, 1), date(2026, 11, 1), RateRangeInvalidError),
        (_day(11, 1), _day(11, 11), RateDateInFutureError),
    ],
)
async def test_a_wrong_range_is_rejected(since: date, until: date, error: type[Exception]) -> None:
    deps, _ = _deps()
    with pytest.raises(error):
        await GetQuoteSeries(deps).execute(RateType.MEP, since, until)


class _Counting:
    def __init__(self) -> None:
        self.calls = 0
        self.down = False

    async def series(self, rate_type: RateType) -> list[Quote]:
        self.calls += 1
        if self.down:
            raise RuntimeError
        return [quote(rate_type, _day(3, 2))]


async def test_the_history_cache_keeps_each_series_for_a_while() -> None:
    inner = _Counting()
    clock = FakeClock()
    clock.current = NOW
    cache = CachedHistoryProvider(inner, clock, ttl=timedelta(minutes=15))

    first = await cache.series(RateType.MEP)
    await cache.series(RateType.MEP)
    await cache.series(RateType.BLUE)
    clock.advance(timedelta(minutes=16))
    await cache.series(RateType.MEP)

    assert first[0].rate_type is RateType.MEP
    assert inner.calls == 3


async def test_the_history_cache_does_not_keep_a_failure() -> None:
    inner = _Counting()
    inner.down = True
    clock = FakeClock()
    cache = CachedHistoryProvider(inner, clock, ttl=timedelta(minutes=15))

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cache.series(RateType.MEP)

    assert inner.calls == 2


def test_the_exact_conversion_rounds_to_the_same_as_the_single_one() -> None:
    mep = quote(RateType.MEP, buy="1560.2", sell="1587.9")
    for money in (
        Money(Decimal("100.00"), Currency.USD),
        Money(Decimal("-100.00"), Currency.USD),
        Money(Decimal("12345.67"), Currency.ARS),
        Money(Decimal("-12345.67"), Currency.ARS),
    ):
        exact = convert_exact(money, mep)
        single = convert(money, mep)
        assert Money.rounded(exact.amount, exact.currency) == single.converted
        assert exact.rate == single.rate


def test_the_day_converter_uses_the_quote_of_each_day() -> None:
    converter = DayConverter(
        Currency.ARS,
        {
            _day(3, 2): quote(RateType.MEP, _day(3, 2), buy="1000", sell="1100"),
            _day(3, 3): quote(RateType.MEP, _day(3, 3), buy="2000", sell="2100"),
        },
    )
    ten = Money(Decimal(10), Currency.USD)

    assert converter.to_target(ten, _day(3, 2)) == Decimal(10000)
    assert converter.to_target(ten, _day(3, 3)) == Decimal(20000)
    # Lo que se debe, a la venta (ADR-0017).
    assert converter.to_target(-ten, _day(3, 3)) == Decimal(-21000)
    assert converter.to_target(ten, _day(3, 4)) is None
    # Lo que ya está en la moneda de destino no necesita cotización.
    assert converter.to_target(Money(Decimal(5), Currency.ARS), _day(9, 9)) == Decimal(5)


def test_bitcoin_is_not_supported_yet() -> None:
    converter = DayConverter(Currency.ARS, {_day(3, 2): quote(RateType.MEP, _day(3, 2))})
    btc = Money(Decimal("0.5"), Currency.BTC)

    assert not converter.supports(Currency.BTC)
    assert converter.supports(Currency.USD)
    assert converter.to_target(btc, _day(3, 2)) is None


async def test_get_converter_brings_the_series_of_the_chosen_dollar() -> None:
    stored = InMemoryQuotes(quote(RateType.BLUE, _day(3, 2), buy="1200", sell="1220"))
    deps, _ = _deps(stored=stored, history=FakeHistoryProvider(down=True))

    converter = await GetConverter(deps).execute(
        Currency.USD, RateType.BLUE, _day(3, 2), _day(3, 2)
    )

    assert converter.to_target(Money(Decimal(1220), Currency.ARS), _day(3, 2)) == Decimal(1)
