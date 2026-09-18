"""API de movimientos y categorías (ADR-0011)."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from rinde.config import Settings
from rinde.main import create_app
from tests.fakes import (
    FakeDatabaseProbe,
    InMemoryAccountsUnitFactory,
    InMemoryAuthUnitFactory,
    InMemoryTransactionsUnitFactory,
)

CSRF = {"X-Requested-With": "rinde"}
PASSPHRASE = "mi gato come fideos los martes"


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    accounts_factory = InMemoryAccountsUnitFactory()
    return create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=InMemoryAuthUnitFactory(),
        accounts_factory=accounts_factory,
        transactions_factory=InMemoryTransactionsUnitFactory(accounts_factory.accounts),
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def signed_in(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/register", json={"username": "mechi", "password": PASSPHRASE}, headers=CSRF
    )
    assert response.status_code == status.HTTP_201_CREATED
    return client


def _account(client: TestClient, currency: str = "ARS") -> str:
    response = client.post(
        "/api/accounts",
        json={"name": f"Cuenta en {currency}", "kind": "bank", "currency": currency},
        headers=CSRF,
    )
    identifier: str = response.json()["id"]
    return identifier


def _category(client: TestClient, kind: str = "expense") -> str:
    categories = client.get("/api/categories").json()
    return str(next(row["id"] for row in categories if row["kind"] == kind))


def _body(client: TestClient, **overrides: Any) -> dict[str, Any]:
    body = {
        "account_id": _account(client),
        "kind": "expense",
        "amount": "15300.50",
        "category_id": _category(client),
        "occurred_on": "2026-09-11",
        "description": "Coto",
    }
    body.update(overrides)
    return body


def test_the_categories_arrive_seeded_the_first_time(signed_in: TestClient) -> None:
    response = signed_in.get("/api/categories")

    assert response.status_code == status.HTTP_200_OK
    categories = response.json()
    slugs = {row["slug"] for row in categories}
    assert {"supermercado", "sueldo", "otros"} <= slugs
    assert {row["kind"] for row in categories} == {"expense", "income"}


def test_a_registered_expense_comes_back_with_its_amount_as_text(signed_in: TestClient) -> None:
    response = signed_in.post("/api/transactions", json=_body(signed_in), headers=CSRF)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    # El monto viaja como string: un número en JSON perdería precisión (ADR-0002).
    assert body["amount"] == "15300.50"
    assert body["currency"] == "ARS"
    assert body["deleted_at"] is None


def test_an_amount_sent_as_a_number_is_rejected(signed_in: TestClient) -> None:
    body = _body(signed_in) | {"amount": 15300.50}

    response = signed_in.post("/api/transactions", json=body, headers=CSRF)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"amount": "0.00"}, "TRANSACTION_AMOUNT_NOT_POSITIVE"),
        ({"amount": "-10.00"}, "TRANSACTION_AMOUNT_NOT_POSITIVE"),
        ({"amount": "10.999"}, "AMOUNT_TOO_PRECISE"),
        ({"occurred_on": "2030-01-01"}, "TRANSACTION_DATE_IN_FUTURE"),
    ],
)
def test_an_invalid_movement_answers_with_its_stable_code(
    signed_in: TestClient, overrides: dict[str, Any], code: str
) -> None:
    body = _body(signed_in) | overrides

    response = signed_in.post("/api/transactions", json=body, headers=CSRF)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == code


def test_an_income_with_an_expense_category_is_rejected(signed_in: TestClient) -> None:
    body = _body(signed_in) | {"kind": "income", "category_id": _category(signed_in, "expense")}

    response = signed_in.post("/api/transactions", json=body, headers=CSRF)

    assert response.json()["code"] == "CATEGORY_KIND_MISMATCH"


def test_a_movement_in_a_dollar_account_cannot_be_loaded_in_pesos(signed_in: TestClient) -> None:
    """La moneda la impone la cuenta: el monto se interpreta en dólares, no en pesos."""
    dollars = _account(signed_in, "USD")

    response = signed_in.post(
        "/api/transactions", json=_body(signed_in, account_id=dollars), headers=CSRF
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["currency"] == "USD"


def test_an_archived_account_does_not_take_movements(signed_in: TestClient) -> None:
    account_id = _account(signed_in)
    signed_in.post(f"/api/accounts/{account_id}/archive", headers=CSRF)

    response = signed_in.post(
        "/api/transactions", json=_body(signed_in, account_id=account_id), headers=CSRF
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["code"] == "ACCOUNT_ARCHIVED"


def test_the_same_idempotency_key_does_not_create_two_movements(signed_in: TestClient) -> None:
    body = _body(signed_in)
    headers = CSRF | {"Idempotency-Key": "clave-1"}

    first = signed_in.post("/api/transactions", json=body, headers=headers)
    second = signed_in.post("/api/transactions", json=body, headers=headers)

    assert first.json()["id"] == second.json()["id"]
    assert len(signed_in.get("/api/transactions").json()["items"]) == 1


def test_the_same_key_with_another_body_is_a_conflict(signed_in: TestClient) -> None:
    headers = CSRF | {"Idempotency-Key": "clave-1"}
    body = _body(signed_in)
    signed_in.post("/api/transactions", json=body, headers=headers)

    response = signed_in.post("/api/transactions", json=body | {"amount": "20.00"}, headers=headers)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_the_balance_of_each_account_comes_from_its_movements(signed_in: TestClient) -> None:
    account_id = _account(signed_in)
    signed_in.post(
        "/api/transactions",
        json=_body(
            signed_in,
            account_id=account_id,
            kind="income",
            amount="100000.00",
            category_id=_category(signed_in, "income"),
        ),
        headers=CSRF,
    )
    signed_in.post(
        "/api/transactions",
        json=_body(signed_in, account_id=account_id, amount="15300.50"),
        headers=CSRF,
    )

    balances = signed_in.get("/api/transactions/balances").json()

    assert balances == [{"account_id": account_id, "amount": "84699.50", "currency": "ARS"}]


def test_the_list_filters_by_account_and_pages(signed_in: TestClient) -> None:
    mine = _account(signed_in)
    other = _account(signed_in, "USD")
    for day in ("09", "10", "11"):
        signed_in.post(
            "/api/transactions",
            json=_body(signed_in, account_id=mine, occurred_on=f"2026-09-{day}"),
            headers=CSRF,
        )
    signed_in.post("/api/transactions", json=_body(signed_in, account_id=other), headers=CSRF)

    first = signed_in.get("/api/transactions", params={"account_id": mine, "limit": 2}).json()
    second = signed_in.get(
        "/api/transactions", params={"account_id": mine, "cursor": first["next_cursor"]}
    ).json()

    assert [row["occurred_on"] for row in first["items"]] == ["2026-09-11", "2026-09-10"]
    assert [row["occurred_on"] for row in second["items"]] == ["2026-09-09"]
    assert second["next_cursor"] is None


def test_an_invented_cursor_is_rejected(signed_in: TestClient) -> None:
    response = signed_in.get("/api/transactions", params={"cursor": "no-es-un-cursor"})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "CURSOR_INVALID"


def test_editing_changes_the_movement_but_not_its_account(signed_in: TestClient) -> None:
    created = signed_in.post("/api/transactions", json=_body(signed_in), headers=CSRF).json()

    response = signed_in.patch(
        f"/api/transactions/{created['id']}",
        json={
            "kind": "expense",
            "amount": "900.00",
            "category_id": created["category_id"],
            "occurred_on": "2026-09-10",
            "description": None,
        },
        headers=CSRF,
    )

    assert response.status_code == status.HTTP_200_OK
    edited = response.json()
    assert edited["amount"] == "900.00"
    assert edited["description"] is None
    assert edited["account_id"] == created["account_id"]


def test_a_deleted_movement_disappears_and_comes_back_with_undo(signed_in: TestClient) -> None:
    created = signed_in.post("/api/transactions", json=_body(signed_in), headers=CSRF).json()

    deleted = signed_in.delete(f"/api/transactions/{created['id']}", headers=CSRF)
    assert deleted.json()["deleted_at"] is not None
    assert signed_in.get(f"/api/transactions/{created['id']}").status_code == 404
    assert signed_in.get("/api/transactions").json()["items"] == []
    assert signed_in.get("/api/transactions/balances").json() == []

    restored = signed_in.post(f"/api/transactions/{created['id']}/restore", headers=CSRF)

    assert restored.json()["deleted_at"] is None
    assert len(signed_in.get("/api/transactions").json()["items"]) == 1


def test_a_category_with_movements_is_not_deleted(signed_in: TestClient) -> None:
    body = _body(signed_in)
    signed_in.post("/api/transactions", json=body, headers=CSRF)

    response = signed_in.delete(f"/api/categories/{body['category_id']}", headers=CSRF)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["code"] == "CATEGORY_IN_USE"


def test_a_new_category_can_be_created_renamed_and_deleted(signed_in: TestClient) -> None:
    created = signed_in.post(
        "/api/categories", json={"name": "Mascotas", "kind": "expense"}, headers=CSRF
    )
    assert created.status_code == status.HTTP_201_CREATED
    assert created.json()["slug"] is None

    renamed = signed_in.patch(
        f"/api/categories/{created.json()['id']}", json={"name": "Veterinaria"}, headers=CSRF
    )
    assert renamed.json()["name"] == "Veterinaria"

    deleted = signed_in.delete(f"/api/categories/{created.json()['id']}", headers=CSRF)
    assert deleted.status_code == status.HTTP_204_NO_CONTENT


def test_a_repeated_category_name_is_a_conflict(signed_in: TestClient) -> None:
    signed_in.post("/api/categories", json={"name": "Mascotas", "kind": "expense"}, headers=CSRF)

    response = signed_in.post(
        "/api/categories", json={"name": " mascotas ", "kind": "expense"}, headers=CSRF
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["code"] == "CATEGORY_NAME_TAKEN"
