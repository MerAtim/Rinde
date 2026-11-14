"""La fuente del IPC, contra respuestas armadas con la forma real.

La forma se copió de lo que devolvía `apis.datos.gob.ar` el 2026-11-14. Si la
fuente cambia de formato, estos tests no se enteran: para eso está la validación,
que la cuenta como caída, y lo guardado en la base.
"""

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from rinde.inflation.application.ports import CpiSourceUnavailableError
from rinde.inflation.domain.cpi import CpiSource
from rinde.inflation.infrastructure.source import SERIES_ID, DatosGobArCpiProvider

pytestmark = pytest.mark.anyio

Handler = Callable[[httpx.Request], httpx.Response]


def _body(data: list[Any]) -> dict[str, Any]:
    return {
        "data": data,
        "count": len(data),
        "meta": [{"frequency": "month"}, {"field": {"id": SERIES_ID}}],
        "params": {"ids": SERIES_ID},
    }


def _provider(handler: Handler) -> DatosGobArCpiProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return DatosGobArCpiProvider(client, base_url="https://apis.example/")


def _json(body: Any, status: int = 200) -> Handler:
    return lambda _: httpx.Response(status, content=json.dumps(body).encode())


async def test_the_whole_series_comes_in_one_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = _body([["2026-09-01", 12514.1508], ["2026-10-01", 12785.9321]])
        return httpx.Response(200, content=json.dumps(body).encode())

    series = await _provider(handler).series()

    assert len(requests) == 1
    url = requests[0].url
    assert url.path == "/series/api/series/"
    assert url.params["ids"] == SERIES_ID
    assert url.params["sort"] == "asc"
    assert [(m.month, m.index, m.source) for m in series] == [
        (date(2026, 9, 1), Decimal("12514.1508"), CpiSource.INDEC),
        (date(2026, 10, 1), Decimal("12785.9321"), CpiSource.INDEC),
    ]


async def test_the_index_is_read_without_float_and_rounded_at_the_border() -> None:
    raw = b'{"data": [["2026-10-01", 12785.93215]]}'

    series = await _provider(lambda _: httpx.Response(200, content=raw)).series()

    assert series[0].index == Decimal("12785.9322")


@pytest.mark.parametrize(
    "broken",
    [
        ["2026-08-15", 100],
        ["2026-08-01", None],
        ["2026-08-01", "12276.766"],
        ["2026-08-01", 0],
        ["2026-08-01", -1],
        ["no es fecha", 100],
        ["2026-08-01"],
        {"fecha": "2026-08-01", "valor": 100},
    ],
    ids=["mitad de mes", "vacio", "texto", "cero", "negativo", "fecha rota", "sin valor", "objeto"],
)
async def test_a_broken_month_is_dropped_alone(broken: Any) -> None:
    series = await _provider(_json(_body([broken, ["2026-10-01", 12785.9321]]))).series()

    assert [m.month for m in series] == [date(2026, 10, 1)]


async def test_a_repeated_month_keeps_the_first() -> None:
    body = _body([["2026-10-01", 1], ["2026-10-01", 2]])

    series = await _provider(_json(body)).series()

    assert [m.index for m in series] == [Decimal(1)]


async def test_the_series_comes_out_sorted() -> None:
    body = _body([["2026-10-01", 2], ["2026-09-01", 1]])

    series = await _provider(_json(body)).series()

    assert [m.month for m in series] == [date(2026, 9, 1), date(2026, 10, 1)]


@pytest.mark.parametrize(
    "body",
    [[], {"datos": []}, {"data": "no"}, "texto"],
    ids=["lista", "sin data", "data no es lista", "texto"],
)
async def test_another_shape_means_the_source_is_down(body: Any) -> None:
    with pytest.raises(CpiSourceUnavailableError):
        await _provider(_json(body)).series()


@pytest.mark.parametrize("status", [404, 500, 429])
async def test_an_error_means_the_source_is_down(status: int) -> None:
    with pytest.raises(CpiSourceUnavailableError):
        await _provider(_json({}, status)).series()
