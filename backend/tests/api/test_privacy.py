"""API de la exportación de los datos, con todos los módulos en memoria (ADR-0034)."""

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rinde.config import Settings
from rinde.main import create_app
from rinde.shared.infrastructure.events import InProcessEventBus
from tests.fakes import (
    FakeClock,
    FakeDatabaseProbe,
    InMemoryAccountsUnitFactory,
    InMemoryAlertsUnitFactory,
    InMemoryAuthUnitFactory,
    InMemoryBudgetsUnitFactory,
    InMemoryImportsUnitFactory,
    InMemoryPreferencesUnitFactory,
    InMemoryRatesUnitFactory,
    InMemoryTransactionsUnitFactory,
)

CSRF = {"X-Requested-With": "rinde"}
PASSPHRASE = "mi gato come fideos los martes"
# Las 12 de Buenos Aires del 10 de noviembre de 2026.
NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)


@pytest.fixture
def auth() -> InMemoryAuthUnitFactory:
    return InMemoryAuthUnitFactory()


@pytest.fixture
def client(settings: Settings, auth: InMemoryAuthUnitFactory) -> Iterator[TestClient]:
    clock = FakeClock()
    clock.current = NOW
    accounts = InMemoryAccountsUnitFactory(clock)
    # El bus real: un gasto evalúa las alertas, como en producción (ADR-0022).
    bus = InProcessEventBus()
    transactions = InMemoryTransactionsUnitFactory(accounts.accounts, clock, events=bus)
    preferences = InMemoryPreferencesUnitFactory()
    rates = InMemoryRatesUnitFactory()
    budgets = InMemoryBudgetsUnitFactory(transactions, preferences, rates, clock)
    app = create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=auth,
        accounts_factory=accounts,
        transactions_factory=transactions,
        rates_factory=rates,
        preferences_factory=preferences,
        budgets_factory=budgets,
        alerts_factory=InMemoryAlertsUnitFactory(transactions, budgets, clock),
        imports_factory=InMemoryImportsUnitFactory(transactions, clock),
        event_bus=bus,
    )
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def _sign_in(client: TestClient, username: str) -> None:
    client.cookies.clear()
    response = client.post(
        "/api/auth/register", json={"username": username, "password": PASSPHRASE}, headers=CSRF
    )
    assert response.status_code == status.HTTP_201_CREATED


def _account(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/accounts", json={"name": name, "kind": "bank", "currency": "ARS"}, headers=CSRF
    )
    assert response.status_code == status.HTTP_201_CREATED
    identifier: str = response.json()["id"]
    return identifier


def _expense_category(client: TestClient) -> str:
    categories: list[dict[str, Any]] = client.get("/api/categories").json()
    identifier: str = next(row["id"] for row in categories if row["kind"] == "expense")
    return identifier


def _spend(client: TestClient, account_id: str, amount: str, description: str) -> str:
    response = client.post(
        "/api/transactions",
        json={
            "account_id": account_id,
            "kind": "expense",
            "amount": amount,
            "category_id": _expense_category(client),
            "occurred_on": "2026-11-09",
            "description": description,
        },
        headers=CSRF,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    identifier: str = response.json()["id"]
    return identifier


def _export(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/privacy/export")
    assert response.status_code == status.HTTP_200_OK, response.text
    body: dict[str, Any] = response.json()
    return body


def test_se_descarga_como_archivo_que_nadie_guarda(client: TestClient) -> None:
    _sign_in(client, "mechi")

    response = client.get("/api/privacy/export")

    assert response.status_code == status.HTTP_200_OK
    # La fecha del nombre es la de hoy en Argentina, con el reloj del sistema.
    assert re.fullmatch(
        r'attachment; filename="rinde-datos-\d{4}-\d{2}-\d{2}\.json"',
        response.headers["content-disposition"],
    )
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["format_version"] == 1
    assert body["profile"]["username"] == "mechi"
    assert body["preferences"] == {
        "reference_currency": "ARS",
        "rate_type": "mep",
        "updated_at": None,
    }


def test_nunca_incluye_los_hashes_de_la_contrasena_ni_del_codigo(
    client: TestClient, auth: InMemoryAuthUnitFactory
) -> None:
    _sign_in(client, "mechi")
    user = next(iter(auth.users.store.values()))

    text = client.get("/api/privacy/export").text

    assert user.password_hash not in text
    assert user.recovery_code_hash not in text
    assert "hash" not in text


def test_incluye_lo_borrado_y_el_historial_de_cambios(client: TestClient) -> None:
    _sign_in(client, "mechi")
    account = _account(client, "Banco")
    kept = _spend(client, account, "1500.50", "Almacén")
    removed = _spend(client, account, "200.00", "Kiosco")
    assert client.delete(f"/api/transactions/{removed}", headers=CSRF).status_code == 200

    ledger = _export(client)["ledger"]

    by_id = {row["id"]: row for row in ledger["transactions"]}
    assert by_id[kept]["money"] == {"amount": "1500.50", "currency": "ARS"}
    assert by_id[kept]["description"] == "Almacén"
    assert by_id[kept]["deleted_at"] is None
    assert by_id[removed]["deleted_at"] is not None
    actions = [(row["subject_id"], row["action"]) for row in ledger["transaction_history"]]
    assert actions == [(kept, "registered"), (removed, "registered"), (removed, "deleted")]


def test_trae_cada_seccion_con_lo_cargado(client: TestClient) -> None:
    _sign_in(client, "mechi")
    banco, efectivo = _account(client, "Banco"), _account(client, "Efectivo")
    category = _expense_category(client)
    client.post(
        "/api/transfers",
        json={
            "from_account_id": banco,
            "to_account_id": efectivo,
            "sent": "5000.00",
            "received": "5000.00",
            "occurred_on": "2026-11-08",
        },
        headers=CSRF,
    )
    client.put(
        f"/api/budgets/{category}", json={"amount": "10000.00", "currency": "ARS"}, headers=CSRF
    )
    client.put(
        "/api/preferences", json={"reference_currency": "USD", "rate_type": "blue"}, headers=CSRF
    )
    # Con el 90 % del tope gastado salta una alerta (ADR-0022).
    _spend(client, banco, "9500.00", "Supermercado")

    body = _export(client)

    assert sorted(row["name"] for row in body["accounts"]) == ["Banco", "Efectivo"]
    [transfer] = body["ledger"]["transfers"]
    assert transfer["sent"] == {"amount": "5000.00", "currency": "ARS"}
    assert any(row["id"] == category for row in body["ledger"]["categories"])
    [budget] = body["budgets"]
    assert budget["category_id"] == category
    assert budget["limit"] == {"amount": "10000.00", "currency": "ARS"}
    assert [alert["category_id"] for alert in body["alerts"]] == [category]
    assert body["preferences"]["reference_currency"] == "USD"
    assert body["imports"] == {"batches": [], "category_rules": []}


def test_no_trae_nada_de_otra_persona(client: TestClient) -> None:
    _sign_in(client, "persona.ajena")
    ajena = _account(client, "Cuenta ajena")
    _spend(client, ajena, "999.00", "Gasto ajeno")
    _sign_in(client, "mechi")

    text = client.get("/api/privacy/export").text

    assert ajena not in text
    assert "Gasto ajeno" not in text
    assert "persona.ajena" not in text
