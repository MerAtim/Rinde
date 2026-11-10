"""Cotizaciones a través de la API."""

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rinde.config import Settings
from rinde.main import create_app
from rinde.rates.domain.quote import RateSource, RateType
from tests.fakes import FakeDatabaseProbe, InMemoryAuthUnitFactory, InMemoryRatesUnitFactory
from tests.unit.rates.fakes import FakeRateProvider, quote

CSRF = {"X-Requested-With": "rinde"}
PAST = date(2026, 3, 2)


@pytest.fixture
def rates() -> InMemoryRatesUnitFactory:
    return InMemoryRatesUnitFactory(
        FakeRateProvider(
            quote(RateType.MEP),
            quote(RateType.BLUE, buy="1535", sell="1555"),
            quote(RateType.MEP, PAST, buy="1190.5", sell="1210", source=RateSource.ARGENTINADATOS),
        )
    )


@pytest.fixture
def client(settings: Settings, rates: InMemoryRatesUnitFactory) -> Iterator[TestClient]:
    app = create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=InMemoryAuthUnitFactory(),
        rates_factory=rates,
    )
    with TestClient(app, base_url="https://testserver") as test_client:
        test_client.post(
            "/api/auth/register",
            json={"username": "mechi", "password": "mi gato come fideos los martes"},
            headers=CSRF,
        )
        yield test_client


def test_today_lists_every_dollar_the_sources_have(client: TestClient) -> None:
    response = client.get("/api/rates")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [
        {
            "rate_type": "mep",
            "base": "USD",
            "counter": "ARS",
            "day": "2026-11-10",
            "buy": "1560.20000000",
            "sell": "1587.90000000",
            "source": "dolarapi",
            "updated_at": None,
        },
        {
            "rate_type": "blue",
            "base": "USD",
            "counter": "ARS",
            "day": "2026-11-10",
            "buy": "1535.00000000",
            "sell": "1555.00000000",
            "source": "dolarapi",
            "updated_at": None,
        },
    ]


def test_a_past_day_is_stored_after_the_first_request(
    client: TestClient, rates: InMemoryRatesUnitFactory
) -> None:
    first = client.get("/api/rates/mep", params={"day": "2026-03-02"})
    rates.provider.down = True
    second = client.get("/api/rates/mep", params={"day": "2026-03-02"})

    assert first.status_code == second.status_code == status.HTTP_200_OK
    assert first.json() == second.json()
    assert (first.json()["sell"], first.json()["source"]) == ("1210.00000000", "argentinadatos")


def test_a_dollar_no_source_has_is_not_found(client: TestClient) -> None:
    response = client.get("/api/rates/ccl")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"code": "RATE_NOT_FOUND"}


def test_with_every_source_down_rates_are_unavailable(
    client: TestClient, rates: InMemoryRatesUnitFactory
) -> None:
    rates.provider.down = True

    response = client.get("/api/rates")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"code": "RATES_UNAVAILABLE"}


def test_a_future_day_is_rejected_with_a_stable_code(client: TestClient) -> None:
    response = client.get("/api/rates", params={"day": "2026-11-11"})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {"code": "RATE_DATE_IN_FUTURE"}


@pytest.mark.parametrize(
    "url", ["/api/rates?day=ayer", "/api/rates?day=2026-02-30", "/api/rates/mayorista"]
)
def test_the_edge_rejects_malformed_input(client: TestClient, url: str) -> None:
    assert client.get(url).status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.parametrize("url", ["/api/rates", "/api/rates/mep"])
def test_without_a_session_rates_are_not_served(
    client: TestClient, rates: InMemoryRatesUnitFactory, url: str
) -> None:
    client.cookies.clear()

    assert client.get(url).status_code == status.HTTP_401_UNAUTHORIZED
    assert rates.provider.requests == []
