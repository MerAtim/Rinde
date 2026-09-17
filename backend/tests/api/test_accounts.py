"""Cuentas a través de la API."""

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rinde.config import Settings
from rinde.main import create_app
from tests.fakes import FakeDatabaseProbe, InMemoryAccountsUnitFactory, InMemoryAuthUnitFactory

CSRF = {"X-Requested-With": "rinde"}


@pytest.fixture
def accounts() -> InMemoryAccountsUnitFactory:
    return InMemoryAccountsUnitFactory()


@pytest.fixture
def client(settings: Settings, accounts: InMemoryAccountsUnitFactory) -> Iterator[TestClient]:
    app = create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=InMemoryAuthUnitFactory(),
        accounts_factory=accounts,
    )
    with TestClient(app, base_url="https://testserver") as test_client:
        test_client.post(
            "/api/auth/register",
            json={"username": "mechi", "password": "mi gato come fideos los martes"},
            headers=CSRF,
        )
        yield test_client


def _open(client: TestClient, **fields: str) -> Any:
    body = {"name": "Galicia sueldo", "kind": "bank", "currency": "ARS", **fields}
    return client.post("/api/accounts", json=body, headers=CSRF)


def test_opening_an_account_returns_it(client: TestClient) -> None:
    response = _open(client)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["name"] == "Galicia sueldo"
    assert (body["kind"], body["currency"], body["archived_at"]) == ("bank", "ARS", None)
    assert client.get(f"/api/accounts/{body['id']}").json() == body


def test_the_list_shows_my_accounts_in_the_order_they_were_opened(
    client: TestClient, accounts: InMemoryAccountsUnitFactory
) -> None:
    _open(client, name="Lemon", kind="crypto_wallet", currency="BTC")
    accounts.clock.advance(timedelta(minutes=1))
    _open(client, name="Efectivo", kind="cash")

    names = [account["name"] for account in client.get("/api/accounts").json()]

    assert names == ["Lemon", "Efectivo"]


def test_archived_accounts_leave_the_list_but_can_be_asked_for(client: TestClient) -> None:
    account_id = _open(client).json()["id"]

    archived = client.post(f"/api/accounts/{account_id}/archive", headers=CSRF)

    assert archived.status_code == status.HTTP_200_OK
    assert archived.json()["archived_at"] is not None
    assert client.get("/api/accounts").json() == []
    assert [a["id"] for a in client.get("/api/accounts?include_archived=true").json()] == [
        account_id
    ]


def test_renaming_an_account(client: TestClient) -> None:
    account_id = _open(client).json()["id"]

    response = client.patch(
        f"/api/accounts/{account_id}", json={"name": "Galicia ahorro"}, headers=CSRF
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "Galicia ahorro"


def test_an_archived_account_cannot_be_renamed(client: TestClient) -> None:
    account_id = _open(client).json()["id"]
    client.post(f"/api/accounts/{account_id}/archive", headers=CSRF)

    response = client.patch(f"/api/accounts/{account_id}", json={"name": "Otro"}, headers=CSRF)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"code": "ACCOUNT_ARCHIVED"}


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"kind": "bank", "currency": "BTC"}, "ACCOUNT_CURRENCY_NOT_ALLOWED"),
        ({"name": "Galicia\u200bsueldo"}, "ACCOUNT_NAME_INVALID"),
    ],
)
def test_domain_rules_answer_with_stable_codes(
    client: TestClient, fields: dict[str, str], code: str
) -> None:
    response = _open(client, **fields)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {"code": code}


@pytest.mark.parametrize(
    "fields",
    [{"currency": "EUR"}, {"kind": "piggy_bank"}, {"name": ""}, {"name": "x" * 61}],
)
def test_the_edge_rejects_malformed_input(client: TestClient, fields: dict[str, str]) -> None:
    assert _open(client, **fields).status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_unknown_fields_are_rejected(client: TestClient) -> None:
    """Un campo de más no se ignora en silencio: puede ser un intento de fijar el dueño."""
    response = client.post(
        "/api/accounts",
        json={"name": "Galicia", "kind": "bank", "currency": "ARS", "owner_id": "otro"},
        headers=CSRF,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
