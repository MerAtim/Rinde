"""Preferencias a través de la API."""

from collections.abc import Iterator

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rinde.config import Settings
from rinde.main import create_app
from tests.fakes import (
    FakeDatabaseProbe,
    InMemoryAuthUnitFactory,
    InMemoryPreferencesUnitFactory,
)

CSRF = {"X-Requested-With": "rinde"}
PASSPHRASE = "mi gato come fideos los martes"


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=InMemoryAuthUnitFactory(),
        preferences_factory=InMemoryPreferencesUnitFactory(),
    )
    with TestClient(app, base_url="https://testserver") as test_client:
        _sign_in(test_client, "mechi")
        yield test_client


def _sign_in(client: TestClient, username: str) -> None:
    client.cookies.clear()
    response = client.post(
        "/api/auth/register", json={"username": username, "password": PASSPHRASE}, headers=CSRF
    )
    assert response.status_code == status.HTTP_201_CREATED


def test_without_choosing_anything_it_is_pesos_at_the_mep(client: TestClient) -> None:
    response = client.get("/api/preferences")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"reference_currency": "ARS", "rate_type": "mep"}


def test_a_change_is_returned_and_kept(client: TestClient) -> None:
    body = {"reference_currency": "USD", "rate_type": "blue"}

    response = client.put("/api/preferences", json=body, headers=CSRF)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == body
    assert client.get("/api/preferences").json() == body


def test_my_preferences_are_not_someone_elses(client: TestClient) -> None:
    client.put(
        "/api/preferences", json={"reference_currency": "USD", "rate_type": "blue"}, headers=CSRF
    )

    _sign_in(client, "intrusa")

    assert client.get("/api/preferences").json() == {
        "reference_currency": "ARS",
        "rate_type": "mep",
    }


@pytest.mark.parametrize(
    "body",
    [
        {"reference_currency": "EUR", "rate_type": "mep"},
        {"reference_currency": "ARS", "rate_type": "mayorista"},
        {"reference_currency": "ARS"},
        {"reference_currency": "ARS", "rate_type": "mep", "owner_id": "otro"},
    ],
)
def test_the_edge_rejects_malformed_input(client: TestClient, body: dict[str, str]) -> None:
    response = client.put("/api/preferences", json=body, headers=CSRF)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_bitcoin_is_rejected_with_a_stable_code(client: TestClient) -> None:
    response = client.put(
        "/api/preferences", json={"reference_currency": "BTC", "rate_type": "mep"}, headers=CSRF
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {"code": "PREFERENCES_CURRENCY_NOT_ALLOWED"}


def test_changing_them_needs_the_csrf_header(client: TestClient) -> None:
    response = client.put(
        "/api/preferences", json={"reference_currency": "USD", "rate_type": "blue"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_without_a_session_there_are_no_preferences(client: TestClient, method: str) -> None:
    client.cookies.clear()

    response = client.request(
        method,
        "/api/preferences",
        json={"reference_currency": "USD", "rate_type": "blue"},
        headers=CSRF,
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
