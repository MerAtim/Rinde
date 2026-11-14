"""API de los movimientos recurrentes (ADR-0027).

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


def _rent(client: TestClient, **overrides: Any) -> dict[str, Any]:
    account = client.post(
        "/api/accounts",
        json={"name": "Galicia", "kind": "bank", "currency": "ARS"},
        headers=CSRF,
    ).json()["id"]
    kind = overrides.get("kind", "expense")
    category = next(
        row["id"] for row in client.get("/api/categories").json() if row["kind"] == kind
    )
    body = {
        "account_id": account,
        "kind": "expense",
        "amount": "450000.00",
        "category_id": category,
        "frequency": "monthly",
        "starts_on": "2026-08-10",
        "description": "Alquiler",
    }
    body.update(overrides)
    return body


def test_a_rule_comes_back_with_what_was_generated_and_the_next_time(client: TestClient) -> None:
    response = client.post("/api/recurring", json=_rent(client), headers=CSRF)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["amount"] == "450000.00"
    assert body["frequency"] == "monthly"
    assert body["generated"] == 2
    assert body["next_on"] == "2026-10-10"
    assert body["cancelled_at"] is None


def test_each_time_is_a_transaction_that_says_which_one_it_is(client: TestClient) -> None:
    rule = client.post("/api/recurring", json=_rent(client), headers=CSRF).json()

    items = client.get("/api/transactions").json()["items"]

    assert [(row["occurred_on"], row["recurrence"], row["installment"]) for row in items] == [
        ("2026-09-10", {"rule_id": rule["id"], "number": 2}, None),
        ("2026-08-10", {"rule_id": rule["id"], "number": 1}, None),
    ]


def test_an_income_is_generated_as_an_income(client: TestClient) -> None:
    body = _rent(client, kind="income", amount="1800000.00", description="Sueldo")

    client.post("/api/recurring", json=body, headers=CSRF)

    assert {row["kind"] for row in client.get("/api/transactions").json()["items"]} == {"income"}


def test_the_due_ones_are_generated_when_asked_and_only_once(
    client: TestClient, clock: FakeClock
) -> None:
    client.post("/api/recurring", json=_rent(client), headers=CSRF)
    clock.current += timedelta(days=31)

    first = client.post("/api/recurring/due", headers=CSRF)
    second = client.post("/api/recurring/due", headers=CSRF)

    assert first.status_code == status.HTTP_200_OK
    assert first.json() == {"created": 1}
    assert second.json() == {"created": 0}
    assert client.get("/api/recurring").json()[0]["generated"] == 3


def test_a_new_amount_counts_from_the_next_time(client: TestClient, clock: FakeClock) -> None:
    rule = client.post("/api/recurring", json=_rent(client), headers=CSRF).json()

    response = client.patch(
        f"/api/recurring/{rule['id']}",
        json={"amount": "520000.00", "description": "Alquiler con aumento"},
        headers=CSRF,
    )
    clock.current += timedelta(days=31)
    client.post("/api/recurring/due", headers=CSRF)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["amount"] == "520000.00"
    amounts = [row["amount"] for row in client.get("/api/transactions").json()["items"]]
    assert amounts == ["520000.00", "450000.00", "450000.00"]


def test_cancelling_keeps_what_passed(client: TestClient, clock: FakeClock) -> None:
    rule = client.post("/api/recurring", json=_rent(client), headers=CSRF).json()

    response = client.post(f"/api/recurring/{rule['id']}/cancel", headers=CSRF)
    clock.current += timedelta(days=31)
    client.post("/api/recurring/due", headers=CSRF)
    change = client.patch(f"/api/recurring/{rule['id']}", json={"amount": "1.00"}, headers=CSRF)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["cancelled_at"] is not None
    assert response.json()["next_on"] is None
    assert len(client.get("/api/transactions").json()["items"]) == 2
    assert change.status_code == status.HTTP_409_CONFLICT
    assert change.json() == {"code": "RECURRING_RULE_CANCELLED"}


def test_the_same_key_returns_the_same_rule(client: TestClient) -> None:
    body = _rent(client)
    headers = {**CSRF, "Idempotency-Key": "alquiler-1"}

    first = client.post("/api/recurring", json=body, headers=headers)
    again = client.post("/api/recurring", json=body, headers=headers)
    other = client.post("/api/recurring", json={**body, "amount": "1.00"}, headers=headers)

    assert again.json()["id"] == first.json()["id"]
    assert len(client.get("/api/recurring").json()) == 1
    assert other.status_code == status.HTTP_409_CONFLICT
    assert other.json() == {"code": "IDEMPOTENCY_KEY_REUSED"}


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"starts_on": "2025-09-10"}, "RECURRING_START_OUT_OF_RANGE"),
        ({"starts_on": "2027-09-12"}, "RECURRING_START_OUT_OF_RANGE"),
        ({"amount": "0.00"}, "TRANSACTION_AMOUNT_NOT_POSITIVE"),
        ({"amount": "1.001"}, "AMOUNT_TOO_PRECISE"),
        ({"kind": "income"}, "CATEGORY_KIND_MISMATCH"),
    ],
    ids=["antes de un año", "después de un año", "cero", "centésimos", "tipo"],
)
def test_an_invalid_rule_is_rejected_with_a_stable_code(
    client: TestClient, overrides: dict[str, str], code: str
) -> None:
    body = _rent(client)
    body.update(overrides)

    response = client.post("/api/recurring", json=body, headers=CSRF)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {"code": code}


def test_an_unknown_frequency_is_rejected_at_the_edge(client: TestClient) -> None:
    response = client.post("/api/recurring", json=_rent(client, frequency="daily"), headers=CSRF)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_without_csrf_nothing_changes(client: TestClient) -> None:
    body = _rent(client)

    response = client.post("/api/recurring", json=body)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert client.get("/api/recurring").json() == []
