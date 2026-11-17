"""El precio del Bitcoin (ADR-0029): fuentes, cadena, pares y conversión en dos pasos.

Las formas de las respuestas se copiaron de lo que devolvían Kraken y Bitstamp
el 2026-11-16.
"""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest

from rinde.rates.application.ports import QuoteRequest, RateSourceUnavailableError
from rinde.rates.application.providers import (
    FallbackHistoryProvider,
    FallbackRateProvider,
    RoutingHistoryProvider,
    RoutingRateProvider,
)
from rinde.rates.domain.errors import QuoteInvalidError
from rinde.rates.domain.quote import Market, Quote, RateSource, kind_of, pair_of
from rinde.rates.infrastructure.bitcoin import BitstampProvider, KrakenProvider
from rinde.rates.infrastructure.sources import ArgentinaDatosProvider
from rinde.shared.domain.money import Currency, Money
from rinde.shared.domain.rate_type import RateType
from tests.fakes import FakeClock, InMemoryRatesUnitFactory
from tests.unit.rates.fakes import FakeHistoryProvider, FakeRateProvider, quote

pytestmark = pytest.mark.anyio

TODAY = date(2026, 11, 10)
NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)
BITCOIN_TODAY = QuoteRequest(TODAY, frozenset({Market.BITCOIN}), current=True)


def _start_of(day: date) -> int:
    """Las 00:00 UTC de un día, en segundos: así marcan las fuentes cada vela."""
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


NOV_8, NOV_9, NOV_10 = (_start_of(date(2026, 11, d)) for d in (8, 9, 10))

KRAKEN_TICKER = {
    "error": [],
    "result": {
        "XXBTZUSD": {
            "a": ["64503.50000", "1", "1.000"],
            "b": ["64503.40000", "3", "3.000"],
            "c": ["64503.70000", "0.00026179"],
            "o": "64813.70000",
        }
    },
}
KRAKEN_OHLC = {
    "error": [],
    "result": {
        "XXBTZUSD": [
            [NOV_8, "64000.1", "65000.0", "63000.0", "64200.5", "64100.0", "900.1", 18000],
            [NOV_9, "64200.5", "65500.0", "63900.0", "65100.0", "64800.0", "850.0", 17000],
            [NOV_10, "65100.0", "65200.0", "64000.0", "64300.0", "64500.0", "120.0", 3000],
        ],
        "last": NOV_9,
    },
}
BITSTAMP_TICKER = {
    "timestamp": str(int((NOW - timedelta(minutes=5)).timestamp())),
    "last": "64486.18",
    "bid": "64486.18",
    "ask": "64486.19",
    "market_type": "SPOT",
}
BITSTAMP_OHLC = {
    "data": {
        "pair": "BTC/USD",
        "ohlc": [
            {"timestamp": str(NOV_8), "open": "64000", "close": "64190.00", "volume": "1"},
            {"timestamp": str(NOV_9), "open": "64190", "close": "65080.00", "volume": "1"},
        ],
    }
}

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _json(body: Any, status: int = 200) -> Handler:
    return lambda _: httpx.Response(status, content=json.dumps(body).encode())


def _clock() -> FakeClock:
    clock = FakeClock()
    clock.current = NOW
    return clock


def _kraken(body: Any) -> KrakenProvider:
    return KrakenProvider(_client(_json(body)), base_url="https://kraken.test")


def _bitstamp(body: Any) -> BitstampProvider:
    return BitstampProvider(_client(_json(body)), _clock(), base_url="https://bitstamp.test")


class TestTheMarketIsNotADollar:
    def test_each_kind_quotes_its_own_pair(self) -> None:
        assert pair_of(Market.BITCOIN) == (Currency.BTC, Currency.USD)
        assert pair_of(RateType.MEP) == (Currency.USD, Currency.ARS)
        assert kind_of("bitcoin") is Market.BITCOIN
        assert kind_of("mep") is RateType.MEP

    @pytest.mark.parametrize(
        ("kind", "base", "counter"),
        [
            (Market.BITCOIN, Currency.USD, Currency.ARS),
            (RateType.MEP, Currency.BTC, Currency.USD),
        ],
    )
    def test_a_quote_with_the_wrong_pair_does_not_exist(
        self, kind: Market | RateType, base: Currency, counter: Currency
    ) -> None:
        with pytest.raises(QuoteInvalidError):
            Quote(
                rate_type=kind,
                day=TODAY,
                buy=Decimal(1),
                sell=Decimal(1),
                source=RateSource.KRAKEN,
                base=base,
                counter=counter,
            )


class TestKraken:
    async def test_today_is_the_bid_and_the_ask(self) -> None:
        found = await _kraken(KRAKEN_TICKER).quotes(BITCOIN_TODAY)

        bitcoin = found[Market.BITCOIN]
        assert (bitcoin.buy, bitcoin.sell) == (Decimal("64503.4"), Decimal("64503.5"))
        assert (bitcoin.base, bitcoin.counter, bitcoin.day) == (Currency.BTC, Currency.USD, TODAY)
        assert bitcoin.source is RateSource.KRAKEN

    async def test_it_is_not_asked_for_dollars_nor_for_past_days(self) -> None:
        def fail(_: httpx.Request) -> httpx.Response:
            raise AssertionError

        kraken = KrakenProvider(_client(fail), base_url="https://kraken.test")

        assert await kraken.quotes(QuoteRequest(TODAY, frozenset({RateType.MEP}), True)) == {}
        assert await kraken.quotes(QuoteRequest(TODAY, frozenset({Market.BITCOIN}), False)) == {}
        assert await kraken.series(RateType.MEP) == []

    @pytest.mark.parametrize(
        "body",
        [
            {"error": ["EQuery:Unknown asset pair"], "result": {}},
            {"error": [], "result": {"OTRO": {}}},
            {"error": [], "result": {"XXBTZUSD": {"a": ["1e5"], "b": ["1"]}}},
            {"error": [], "result": {"XXBTZUSD": {"a": [], "b": []}}},
            ["no", "es", "un", "objeto"],
        ],
    )
    async def test_an_answer_with_another_shape_is_a_source_down(self, body: Any) -> None:
        with pytest.raises(RateSourceUnavailableError):
            await _kraken(body).quotes(BITCOIN_TODAY)

    async def test_a_bid_above_the_ask_is_discarded_not_believed(self) -> None:
        crossed = {"error": [], "result": {"XXBTZUSD": {"a": ["64000.0"], "b": ["64100.0"]}}}
        stamp = {**BITSTAMP_TICKER, "bid": "64100.00", "ask": "64000.00"}

        assert await _kraken(crossed).quotes(BITCOIN_TODAY) == {}
        assert await _bitstamp(stamp).quotes(BITCOIN_TODAY) == {}

    async def test_the_series_takes_each_close_as_the_price_of_its_day(self) -> None:
        series = await _kraken(KRAKEN_OHLC).series(Market.BITCOIN)

        # Cada vela empieza a las 00:00 UTC de su día, y su cierre es el precio de ese día.
        assert [(q.day, q.buy, q.sell) for q in series] == [
            (date(2026, 11, 8), Decimal("64200.5"), Decimal("64200.5")),
            (date(2026, 11, 9), Decimal("65100"), Decimal("65100")),
            (date(2026, 11, 10), Decimal("64300"), Decimal("64300")),
        ]

    async def test_a_broken_candle_is_dropped_alone(self) -> None:
        body = {
            "error": [],
            "result": {
                "XXBTZUSD": [
                    "no es una vela",
                    [str(NOV_8), "1", "1", "1", "64200.5"],
                    [NOV_9, "1", "1", "1", "-3"],
                    [NOV_10, "1", "1", "1", "64300.0"],
                ]
            },
        }

        series = await _kraken(body).series(Market.BITCOIN)

        assert [q.day for q in series] == [date(2026, 11, 10)]

    async def test_a_series_that_is_not_a_list_is_a_source_down(self) -> None:
        with pytest.raises(RateSourceUnavailableError):
            await _kraken({"error": [], "result": {"XXBTZUSD": {}}}).series(Market.BITCOIN)


class TestBitstamp:
    async def test_today_is_the_bid_and_the_ask_with_its_moment(self) -> None:
        bitcoin = (await _bitstamp(BITSTAMP_TICKER).quotes(BITCOIN_TODAY))[Market.BITCOIN]

        assert (bitcoin.buy, bitcoin.sell) == (Decimal("64486.18"), Decimal("64486.19"))
        assert bitcoin.updated_at == NOW - timedelta(minutes=5)
        assert bitcoin.source is RateSource.BITSTAMP

    async def test_a_price_older_than_an_hour_is_not_today(self) -> None:
        stale = {**BITSTAMP_TICKER, "timestamp": str(int((NOW - timedelta(hours=2)).timestamp()))}

        assert await _bitstamp(stale).quotes(BITCOIN_TODAY) == {}

    @pytest.mark.parametrize(
        "body",
        [
            {**BITSTAMP_TICKER, "bid": 64486.18},
            {**BITSTAMP_TICKER, "ask": "mucho"},
            {**BITSTAMP_TICKER, "timestamp": "ayer"},
            {"error": "algo"},
        ],
    )
    async def test_an_answer_with_another_shape_is_a_source_down(self, body: Any) -> None:
        with pytest.raises(RateSourceUnavailableError):
            await _bitstamp(body).quotes(BITCOIN_TODAY)

    async def test_the_series_takes_each_close_and_drops_what_is_broken(self) -> None:
        body = {
            "data": {"ohlc": [*BITSTAMP_OHLC["data"]["ohlc"], {"timestamp": "x", "close": "1"}]}
        }

        series = await _bitstamp(body).series(Market.BITCOIN)

        assert [(q.day, q.buy) for q in series] == [
            (date(2026, 11, 8), Decimal("64190")),
            (date(2026, 11, 9), Decimal("65080")),
        ]
        assert await _bitstamp(body).series(RateType.BLUE) == []

    async def test_a_series_with_another_shape_is_a_source_down(self) -> None:
        with pytest.raises(RateSourceUnavailableError):
            await _bitstamp({"data": "nada"}).series(Market.BITCOIN)


class TestTheChain:
    async def test_dollars_and_bitcoin_go_each_to_their_own_sources(self) -> None:
        dollars = FakeRateProvider(quote(RateType.MEP, TODAY))
        markets = FakeRateProvider(quote(Market.BITCOIN, TODAY, buy="64000", sell="64010"))
        routing = RoutingRateProvider(dollars, markets)

        found = await routing.quotes(
            QuoteRequest(TODAY, frozenset({RateType.MEP, Market.BITCOIN}), current=True)
        )

        assert set(found) == {RateType.MEP, Market.BITCOIN}
        assert [r.types for r in dollars.requests] == [frozenset({RateType.MEP})]
        assert [r.types for r in markets.requests] == [frozenset({Market.BITCOIN})]

    async def test_one_chain_down_does_not_take_the_other_with_it(self) -> None:
        routing = RoutingRateProvider(
            FakeRateProvider(quote(RateType.MEP, TODAY)), FakeRateProvider(down=True)
        )
        both = QuoteRequest(TODAY, frozenset({RateType.MEP, Market.BITCOIN}), current=True)

        assert set(await routing.quotes(both)) == {RateType.MEP}
        with pytest.raises(RateSourceUnavailableError):
            await routing.quotes(QuoteRequest(TODAY, frozenset({Market.BITCOIN}), current=True))

    async def test_if_kraken_is_down_bitstamp_answers(self) -> None:
        chain = FallbackRateProvider(
            [
                ("kraken", FakeRateProvider(down=True)),
                ("bitstamp", FakeRateProvider(quote(Market.BITCOIN, TODAY))),
            ]
        )

        assert Market.BITCOIN in await chain.quotes(BITCOIN_TODAY)

    async def test_the_series_comes_whole_from_the_first_source_that_has_it(self) -> None:
        bitstamp = FakeHistoryProvider(quote(Market.BITCOIN, date(2026, 11, 8)))
        history = FallbackHistoryProvider(
            [
                ("kraken", FakeHistoryProvider(down=True)),
                ("empty", FakeHistoryProvider()),
                ("bitstamp", bitstamp),
            ]
        )

        assert [q.day for q in await history.series(Market.BITCOIN)] == [date(2026, 11, 8)]
        with pytest.raises(RateSourceUnavailableError):
            await FallbackHistoryProvider([("kraken", FakeHistoryProvider())]).series(
                Market.BITCOIN
            )

    async def test_each_series_goes_to_its_own_source(self) -> None:
        dollars = FakeHistoryProvider(quote(RateType.MEP, date(2026, 11, 8)))
        markets = FakeHistoryProvider(quote(Market.BITCOIN, date(2026, 11, 8)))
        routing = RoutingHistoryProvider(dollars, markets)

        await routing.series(RateType.MEP)
        await routing.series(Market.BITCOIN)

        assert (dollars.requests, markets.requests) == ([RateType.MEP], [Market.BITCOIN])

    async def test_the_dollar_source_ignores_bitcoin(self) -> None:
        def fail(_: httpx.Request) -> httpx.Response:
            raise AssertionError

        source = ArgentinaDatosProvider(_client(fail), base_url="https://argentinadatos.test")

        assert await source.quotes(QuoteRequest(TODAY, frozenset({Market.BITCOIN}), False)) == {}
        assert await source.series(Market.BITCOIN) == []


class TestTheConverter:
    async def test_it_brings_only_the_series_it_needs(self) -> None:
        rates = InMemoryRatesUnitFactory(
            FakeRateProvider(
                quote(RateType.MEP, TODAY, buy="1500", sell="1550"),
                quote(Market.BITCOIN, TODAY, buy="60000", sell="60100"),
            ),
            FakeHistoryProvider(
                quote(RateType.MEP, date(2026, 11, 9), buy="1400", sell="1450"),
                quote(Market.BITCOIN, date(2026, 11, 9), buy="50000", sell="50000"),
            ),
        )
        since, until = date(2026, 11, 9), TODAY

        async with rates() as unit:
            pesos_only = await unit.converter.execute(
                Currency.USD, RateType.MEP, since, until, frozenset({Currency.ARS})
            )
            with_bitcoin = await unit.converter.execute(
                Currency.ARS, RateType.MEP, since, until, frozenset({Currency.BTC})
            )

        assert set(pesos_only.series) == {RateType.MEP}
        assert not pesos_only.supports(Currency.BTC)
        assert set(with_bitcoin.series) == {RateType.MEP, Market.BITCOIN}
        half = Money(Decimal("0.5"), Currency.BTC)
        # Ayer: 0,5 a 50.000 y a 1.400. Hoy: 0,5 a 60.000 y a 1.500.
        assert with_bitcoin.to_target(half, date(2026, 11, 9)) == Decimal(35_000_000)
        assert with_bitcoin.to_target(half, TODAY) == Decimal(45_000_000)
        # Lo que se debe, del lado prudente en los dos pasos: la venta de cada uno.
        assert with_bitcoin.to_target(-half, TODAY) == Decimal(-46_577_500)
