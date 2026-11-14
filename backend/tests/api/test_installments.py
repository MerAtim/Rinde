"""API de las compras en cuotas (ADR-0026).

El reloj de prueba marca el 11 de septiembre de 2026, a las 9 de Buenos Aires.
"""

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from rinde.config import Settings
from rinde.main import create_app
from tests.fakes import (
    FakeClock,
    FakeDatabaseProbe,
    InMemoryAccountsUnitFactory,
    InMemoryAuthUnitFactory,
    InMemoryTransactionsUnitFactory,
)

CSRF = {"X-Requested-With": "rinde"}
PASSPHRASE = "mi gato come fideos los martes"


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def app(settings: Settings, clock: FakeClock) -> FastAPI:
    accounts_factory = InMemoryAccountsUnitFactory()
    return create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=InMemoryAuthUnitFactory(),
        accounts_factory=accounts_factory,
        transactions_factory=InMemoryTransactionsUnitFactory(accounts_factory.accounts, clock),
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url="https://testserver") as test_client:
        response = test_client.post(
            "/api/auth/register", json={"username": "mechi", "password": PASSPHRASE}, headers=CSRF
        )
        assert response.status_code == status.HTTP_201_CREATED
        yield test_client


def _purchase(client: TestClient, **overrides: Any) -> dict[str, Any]:
    account = client.post(
        "/api/accounts",
        json={"name": "Visa", "kind": "credit_card", "currency": "ARS"},
        headers=CSRF,
    ).json()["id"]
    category = next(
        row["id"] for row in client.get("/api/categories").json() if row["kind"] == "expense"
    )
    body = {
        "account_id": account,
        "category_id": category,
        "total": "100000.00",
        "count": 3,
        "first_on": "2026-08-11",
        "description": "Lavarropas",
    }
    body.update(overrides)
    return body


def test_a_purchase_comes_back_with_its_schedule_and_what_is_left(client: TestClient) -> None:
    response = client.post("/api/installments", json=_purchase(client), headers=CSRF)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["total"] == "100000.00"
    assert body["pending"] == "33333.33"
    assert [(item["number"], item["due_on"], item["amount"]) for item in body["installments"]] == [
        (1, "2026-08-11", "33333.34"),
        (2, "2026-09-11", "33333.33"),
        (3, "2026-10-11", "33333.33"),
    ]
    assert [item["transaction_id"] is not None for item in body["installments"]] == [
        True,
        True,
        False,
    ]
    assert client.get("/api/installments").json() == [body]


def test_each_installment_is_a_transaction_that_says_which_one_it_is(client: TestClient) -> None:
    plan = client.post("/api/installments", json=_purchase(client), headers=CSRF).json()

    items = client.get("/api/transactions").json()["items"]

    assert [(row["amount"], row["installment"]) for row in items] == [
        ("33333.33", {"plan_id": plan["id"], "number": 2, "count": 3}),
        ("33333.34", {"plan_id": plan["id"], "number": 1, "count": 3}),
    ]


def test_the_due_ones_are_generated_when_asked_and_only_once(
    client: TestClient, clock: FakeClock
) -> None:
    client.post("/api/installments", json=_purchase(client), headers=CSRF)
    clock.current += timedelta(days=31)

    first = client.post("/api/installments/due", headers=CSRF)
    second = client.post("/api/installments/due", headers=CSRF)

    assert first.status_code == status.HTTP_200_OK
    assert first.json() == {"created": 1}
    assert second.json() == {"created": 0}
    assert client.get("/api/installments").json()[0]["pending"] == "0.00"


def test_cancelling_keeps_what_was_paid(client: TestClient, clock: FakeClock) -> None:
    plan = client.post("/api/installments", json=_purchase(client), headers=CSRF).json()

    response = client.post(f"/api/installments/{plan['id']}/cancel", headers=CSRF)
    clock.current += timedelta(days=31)
    client.post("/api/installments/due", headers=CSRF)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["cancelled_at"] is not None
    assert response.json()["pending"] == "0.00"
    assert len(client.get("/api/transactions").json()["items"]) == 2


def test_the_same_key_returns_the_same_plan(client: TestClient) -> None:
    body = _purchase(client)
    headers = {**CSRF, "Idempotency-Key": "compra-1"}

    first = client.post("/api/installments", json=body, headers=headers)
    second = client.post("/api/installments", json=body, headers=headers)
    other = client.post("/api/installments", json={**body, "count": 6}, headers=headers)

    assert second.json()["id"] == first.json()["id"]
    assert len(client.get("/api/installments").json()) == 1
    assert other.status_code == status.HTTP_409_CONFLICT
    assert other.json() == {"code": "IDEMPOTENCY_KEY_REUSED"}


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"total": "0.02"}, "INSTALLMENT_AMOUNT_TOO_SMALL"),
        ({"first_on": "2026-12-01"}, "TRANSACTION_DATE_IN_FUTURE"),
        ({"total": "10.001"}, None),
        ({"count": 1}, None),
        ({"count": 49}, None),
    ],
    ids=["no alcanza un centavo", "fecha futura", "mas decimales", "una cuota", "49 cuotas"],
)
def test_an_invalid_purchase_is_rejected_with_a_stable_code(
    client: TestClient, overrides: dict[str, Any], code: str | None
) -> None:
    response = client.post("/api/installments", json=_purchase(client, **overrides), headers=CSRF)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    if code is not None:
        assert response.json() == {"code": code}


def test_without_csrf_nothing_changes(client: TestClient) -> None:
    response = client.post("/api/installments/due")

    assert response.status_code == status.HTTP_403_FORBIDDEN
