"""Adaptadores de las fuentes, contra respuestas armadas con la forma real.

Las formas de las respuestas se copiaron de lo que devolvían las fuentes el
2026-11-10. Si una fuente cambia su formato, estos tests no se enteran: para eso
están la validación y el respaldo a la fuente siguiente.
"""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest

from rinde.rates.application.ports import QuoteRequest, RateSourceUnavailableError
from rinde.rates.domain.quote import RateSource
from rinde.rates.infrastructure.http import MAX_RESPONSE_BYTES, get_json
from rinde.rates.infrastructure.sources import (
    SERIES_MAX_BYTES,
    ArgentinaDatosProvider,
    CriptoYaProvider,
    DolarApiProvider,
)
from rinde.shared.domain.rate_type import ALL_RATE_TYPES, RateType
from tests.fakes import FakeClock

pytestmark = pytest.mark.anyio

TODAY = date(2026, 11, 10)
NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)
CURRENT = QuoteRequest(TODAY, ALL_RATE_TYPES, current=True)

DOLARAPI = [
    {"moneda": "USD", "casa": "oficial", "nombre": "Oficial", "compra": 1520, "venta": 1570,
     "fechaActualizacion": "2026-11-05T18:55:00.000Z"},
    {"moneda": "USD", "casa": "blue", "nombre": "Blue", "compra": 1535, "venta": 1555,
     "fechaActualizacion": "2026-11-10T11:54:00.000Z"},
    {"moneda": "USD", "casa": "bolsa", "nombre": "Bolsa", "compra": 1560.2, "venta": 1587.9,
     "fechaActualizacion": "2026-11-10T11:54:00.000Z"},
    {"moneda": "USD", "casa": "contadoconliqui", "nombre": "CCL", "compra": 1658.4,
     "venta": 1664.9, "fechaActualizacion": "2026-11-10T11:54:00.000Z"},
    {"moneda": "USD", "casa": "mayorista", "nombre": "Mayorista", "compra": 1536.5,
     "venta": 1545.5, "fechaActualizacion": "2026-11-05T18:06:00.000Z"},
    {"moneda": "USD", "casa": "cripto", "nombre": "Cripto", "compra": 1653.44,
     "venta": 1657.69, "fechaActualizacion": "2026-11-10T11:54:00.000Z"},
    {"moneda": "USD", "casa": "tarjeta", "nombre": "Tarjeta", "compra": 1976, "venta": 2041,
     "fechaActualizacion": "2026-11-05T18:55:00.000Z"},
]  # fmt: skip

CRIPTOYA = {
    "mayorista": {"price": 1545.5, "variation": 0, "timestamp": 1793905300},
    "oficial": {"price": 1570, "ask": 1570, "bid": 1520, "variation": 0, "timestamp": 1794314450},
    "tarjeta": {"price": 2041, "variation": 0, "timestamp": 1794314450},
    "blue": {"ask": 1555, "bid": 1535, "variation": 0, "timestamp": 1794314721},
    "mep": {"al30": {"ci": {"price": 1583.82, "variation": 0.68, "timestamp": 1794254346}}},
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


async def test_dolarapi_translates_every_dollar_but_the_wholesale_one() -> None:
    async with _client(_json(DOLARAPI)) as client:
        result = await DolarApiProvider(client, _clock(), base_url="https://x").quotes(CURRENT)

    assert result.keys() == ALL_RATE_TYPES
    mep = result[RateType.MEP]
    # Leído como Decimal desde el texto: 1587.9 no pasó nunca por un float.
    assert (mep.buy, mep.sell) == (Decimal("1560.2"), Decimal("1587.9"))
    assert mep.day == TODAY
    assert mep.source is RateSource.DOLARAPI
    # El oficial es del jueves: se informa la fecha real, no se disfraza de hoy.
    assert result[RateType.OFFICIAL].updated_at == datetime(2026, 11, 5, 18, 55, tzinfo=UTC)


async def test_dolarapi_has_no_history() -> None:
    def fail(_: httpx.Request) -> httpx.Response:
        raise AssertionError

    async with _client(fail) as client:
        provider = DolarApiProvider(client, _clock(), base_url="https://x")
        assert await provider.quotes(QuoteRequest(TODAY, ALL_RATE_TYPES, current=False)) == {}


@pytest.mark.parametrize(
    "broken",
    [
        {"compra": 1600, "venta": 1500},  # compra mayor que venta
        {"compra": -1},
        {"compra": "1560.2"},  # string donde va un número
        {"compra": True},
        {"venta": None},
        {"fechaActualizacion": "2026-11-10T11:54:00"},  # sin zona horaria
        {"fechaActualizacion": "2026-10-01T11:54:00.000Z"},  # trabada hace semanas
    ],
)
async def test_dolarapi_drops_only_the_broken_item(broken: dict[str, Any]) -> None:
    body = [item | broken if item["casa"] == "bolsa" else item for item in DOLARAPI]

    async with _client(_json(body)) as client:
        result = await DolarApiProvider(client, _clock(), base_url="https://x").quotes(CURRENT)

    assert RateType.MEP not in result
    assert RateType.BLUE in result


@pytest.mark.parametrize("body", [{"error": "x"}, "texto", None])
async def test_dolarapi_with_another_shape_is_down(body: Any) -> None:
    async with _client(_json(body)) as client:
        provider = DolarApiProvider(client, _clock(), base_url="https://x")
        with pytest.raises(RateSourceUnavailableError):
            await provider.quotes(CURRENT)


async def test_argentinadatos_asks_one_day_per_dollar() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        casa = request.url.path.split("/")[4]
        body = {"casa": casa, "compra": 1190.5, "venta": 1210, "fecha": "2026-03-02"}
        return httpx.Response(200, content=json.dumps(body).encode())

    request = QuoteRequest(date(2026, 3, 2), frozenset({RateType.MEP, RateType.CCL}), False)
    async with _client(handler) as client:
        result = await ArgentinaDatosProvider(client, base_url="https://x").quotes(request)

    assert sorted(seen) == [
        "/v1/cotizaciones/dolares/bolsa/2026/03/02",
        "/v1/cotizaciones/dolares/contadoconliqui/2026/03/02",
    ]
    assert result[RateType.MEP].sell == Decimal(1210)
    assert result[RateType.MEP].updated_at is None
    assert result[RateType.MEP].source is RateSource.ARGENTINADATOS


async def test_argentinadatos_without_that_day_has_nothing() -> None:
    request = QuoteRequest(date(2015, 3, 2), frozenset({RateType.MEP}), False)
    async with _client(_json({"error": "Not found"}, 404)) as client:
        assert await ArgentinaDatosProvider(client, base_url="https://x").quotes(request) == {}


async def test_argentinadatos_answering_another_day_is_not_trusted() -> None:
    body = {"casa": "bolsa", "compra": 1190.5, "venta": 1210, "fecha": "2026-03-01"}
    request = QuoteRequest(date(2026, 3, 2), frozenset({RateType.MEP}), False)
    async with _client(_json(body)) as client:
        provider = ArgentinaDatosProvider(client, base_url="https://x")
        with pytest.raises(RateSourceUnavailableError):
            await provider.quotes(request)


async def test_argentinadatos_with_one_failure_still_returns_the_rest() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        casa = request.url.path.split("/")[4]
        if casa == "bolsa":
            return httpx.Response(500)
        body = {"casa": casa, "compra": 1535, "venta": 1555, "fecha": "2026-03-02"}
        return httpx.Response(200, content=json.dumps(body).encode())

    request = QuoteRequest(date(2026, 3, 2), frozenset({RateType.MEP, RateType.BLUE}), False)
    async with _client(handler) as client:
        result = await ArgentinaDatosProvider(client, base_url="https://x").quotes(request)

    assert result.keys() == {RateType.BLUE}


async def test_criptoya_only_covers_the_official_and_the_blue() -> None:
    async with _client(_json(CRIPTOYA)) as client:
        result = await CriptoYaProvider(client, _clock(), base_url="https://x").quotes(CURRENT)

    assert result.keys() == {RateType.OFFICIAL, RateType.BLUE}
    assert (result[RateType.BLUE].buy, result[RateType.BLUE].sell) == (Decimal(1535), Decimal(1555))
    assert result[RateType.BLUE].source is RateSource.CRIPTOYA


async def test_criptoya_is_not_asked_for_what_it_does_not_publish() -> None:
    def fail(_: httpx.Request) -> httpx.Response:
        raise AssertionError

    request = QuoteRequest(TODAY, frozenset({RateType.MEP, RateType.CCL}), current=True)
    async with _client(fail) as client:
        assert await CriptoYaProvider(client, _clock(), base_url="https://x").quotes(request) == {}


async def test_criptoya_with_a_broken_timestamp_drops_the_item() -> None:
    body = CRIPTOYA | {"blue": {"ask": 1555, "bid": 1535, "timestamp": 10**30}}
    async with _client(_json(body)) as client:
        result = await CriptoYaProvider(client, _clock(), base_url="https://x").quotes(CURRENT)

    assert result.keys() == {RateType.OFFICIAL}


async def test_a_server_error_is_retried_once_and_then_the_source_is_down() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    async with _client(handler) as client:
        with pytest.raises(RateSourceUnavailableError):
            await get_json(client, "https://x/", timeout_seconds=1, backoff_seconds=0)

    assert calls == 2


async def test_a_retry_that_works_is_enough() -> None:
    responses = iter([httpx.Response(504), httpx.Response(200, content=b"[1.5]")])
    async with _client(lambda _: next(responses)) as client:
        assert await get_json(client, "https://x/", timeout_seconds=1, backoff_seconds=0) == [
            Decimal("1.5")
        ]


async def test_a_timeout_is_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("lento", request=request)

    async with _client(handler) as client:
        with pytest.raises(RateSourceUnavailableError):
            await get_json(client, "https://x/", timeout_seconds=1, backoff_seconds=0)

    assert calls == 2


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429),
        httpx.Response(403),
        httpx.Response(200, content=b"<html>mantenimiento</html>"),
        httpx.Response(200, content=b" " * (MAX_RESPONSE_BYTES + 1)),
    ],
)
async def test_what_is_not_a_quote_is_not_retried(response: httpx.Response) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response

    async with _client(handler) as client:
        with pytest.raises(RateSourceUnavailableError):
            await get_json(client, "https://x/", timeout_seconds=1, backoff_seconds=0)

    assert calls == 1


# La forma real de la serie: una lista con un elemento por día, del más viejo al
# más nuevo. Recortada: la real empieza en 2018 y tiene unos 2.900 días.
SERIES = [
    {"casa": "bolsa", "compra": 1540.1, "venta": 1567.3, "fecha": "2026-11-06"},
    {"casa": "bolsa", "compra": 1540.1, "venta": 1567.3, "fecha": "2026-11-07"},
    {"casa": "bolsa", "compra": 1551, "venta": 1578.2, "fecha": "2026-11-09"},
    {"casa": "bolsa", "compra": 1560.2, "venta": 1587.9, "fecha": "2026-11-10"},
]


async def test_argentinadatos_brings_the_whole_series_in_one_request() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, content=json.dumps(SERIES).encode())

    async with _client(handler) as client:
        series = await ArgentinaDatosProvider(client, base_url="https://x").series(RateType.MEP)

    assert seen == ["/v1/cotizaciones/dolares/bolsa"]
    assert [q.day for q in series] == [
        date(2026, 11, 6),
        date(2026, 11, 7),
        date(2026, 11, 9),
        date(2026, 11, 10),
    ]
    assert series[-1].buy == Decimal("1560.2")
    assert {q.source for q in series} == {RateSource.ARGENTINADATOS}


@pytest.mark.parametrize(
    "broken",
    [
        {"casa": "bolsa", "compra": "1551", "venta": 1578.2, "fecha": "2026-11-08"},
        {"casa": "bolsa", "compra": 1600, "venta": 1500, "fecha": "2026-11-08"},
        {"casa": "blue", "compra": 1535, "venta": 1555, "fecha": "2026-11-08"},
        {"casa": "bolsa", "compra": 1551, "venta": 1578.2, "fecha": "ayer"},
    ],
)
async def test_argentinadatos_series_drops_only_the_broken_days(broken: dict[str, Any]) -> None:
    async with _client(_json([*SERIES, broken])) as client:
        series = await ArgentinaDatosProvider(client, base_url="https://x").series(RateType.MEP)

    assert date(2026, 11, 8) not in {q.day for q in series}
    assert len(series) == len(SERIES)


async def test_argentinadatos_series_keeps_the_first_of_a_repeated_day() -> None:
    repeated = {"casa": "bolsa", "compra": 1, "venta": 2, "fecha": "2026-11-10"}
    async with _client(_json([*SERIES, repeated])) as client:
        series = await ArgentinaDatosProvider(client, base_url="https://x").series(RateType.MEP)

    assert series[-1].buy == Decimal("1560.2")


@pytest.mark.parametrize("body", [{"casa": "bolsa"}, "serie", None])
async def test_argentinadatos_series_with_another_shape_is_down(body: Any) -> None:
    async with _client(_json(body)) as client:
        provider = ArgentinaDatosProvider(client, base_url="https://x")
        with pytest.raises(RateSourceUnavailableError):
            await provider.series(RateType.MEP)


async def test_the_series_may_be_larger_than_a_quote_but_not_unbounded() -> None:
    big = [SERIES[0]] * ((MAX_RESPONSE_BYTES // len(json.dumps(SERIES[0]))) + 10)
    assert len(json.dumps(big)) > MAX_RESPONSE_BYTES
    async with _client(_json(big)) as client:
        series = await ArgentinaDatosProvider(client, base_url="https://x").series(RateType.MEP)
    assert len(series) == 1

    async with _client(lambda _: httpx.Response(200, content=b" " * (SERIES_MAX_BYTES + 1))) as c:
        with pytest.raises(RateSourceUnavailableError):
            await ArgentinaDatosProvider(c, base_url="https://x").series(RateType.MEP)
