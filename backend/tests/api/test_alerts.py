"""API de alertas, de punta a punta con el bus real y los otros módulos en memoria (ADR-0022)."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rinde.alerts.application.ports import MonthReading
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
    InMemoryPreferencesUnitFactory,
    InMemoryRatesUnitFactory,
    InMemoryTransactionsUnitFactory,
)

CSRF = {"X-Requested-With": "rinde"}
PASSPHRASE = "mi gato come fideos los martes"
# Las 12 de Buenos Aires del 10 de noviembre de 2026.
NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)


class BrokenBudgets:
    """Como si presupuestos fallara al medir, por ejemplo sin cotizaciones."""

    async def current_month(self, owner_id: UUID) -> MonthReading:
        raise RuntimeError("sin cotización")


@pytest.fixture
def app_parts(settings: Settings) -> dict[str, Any]:
    clock = FakeClock()
    clock.current = NOW
    bus = InProcessEventBus()
    accounts = InMemoryAccountsUnitFactory()
    transactions = InMemoryTransactionsUnitFactory(accounts.accounts, clock, events=bus)
    preferences = InMemoryPreferencesUnitFactory()
    rates = InMemoryRatesUnitFactory()
    budgets = InMemoryBudgetsUnitFactory(transactions, preferences, rates, clock)
    alerts = InMemoryAlertsUnitFactory(transactions, budgets, clock)
    app = create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=InMemoryAuthUnitFactory(),
        accounts_factory=accounts,
        transactions_factory=transactions,
        rates_factory=rates,
        preferences_factory=preferences,
        budgets_factory=budgets,
        alerts_factory=alerts,
        event_bus=bus,
    )
    return {"app": app, "clock": clock, "alerts": alerts}


@pytest.fixture
def client(app_parts: dict[str, Any]) -> Iterator[TestClient]:
    with TestClient(app_parts["app"], base_url="https://testserver") as test_client:
        _sign_in(test_client, "mechi")
        yield test_client


def _sign_in(client: TestClient, username: str) -> None:
    client.cookies.clear()
    response = client.post(
        "/api/auth/register", json={"username": username, "password": PASSPHRASE}, headers=CSRF
    )
    assert response.status_code == status.HTTP_201_CREATED


def _expense_category(client: TestClient) -> str:
    categories: list[dict[str, Any]] = client.get("/api/categories").json()
    identifier: str = next(row["id"] for row in categories if row["kind"] == "expense")
    return identifier


def _account(client: TestClient) -> str:
    response = client.post(
        "/api/accounts",
        json={"name": "Banco", "kind": "bank", "currency": "ARS"},
        headers=CSRF,
    )
    identifier: str = response.json()["id"]
    return identifier


def _spend(client: TestClient, account: str, category: str, amount: str, day: str) -> str:
    response = client.post(
        "/api/transactions",
        json={
            "account_id": account,
            "kind": "expense",
            "amount": amount,
            "category_id": category,
            "occurred_on": day,
        },
        headers=CSRF,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    identifier: str = response.json()["id"]
    return identifier


def _budget(client: TestClient, category: str, amount: str) -> None:
    response = client.put(
        f"/api/budgets/{category}", json={"amount": amount, "currency": "ARS"}, headers=CSRF
    )
    assert response.status_code == status.HTTP_200_OK


def test_without_alerts_the_feed_is_empty(client: TestClient) -> None:
    response = client.get("/api/alerts")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"unread": 0, "alerts": []}


def test_an_expense_that_reaches_80_percent_raises_an_alert(client: TestClient) -> None:
    food = _expense_category(client)
    account = _account(client)
    _budget(client, food, "1000.00")
    _spend(client, account, food, "500.00", "2026-11-05")
    assert client.get("/api/alerts").json()["unread"] == 0

    _spend(client, account, food, "350.00", "2026-11-09")
    feed = client.get("/api/alerts").json()

    assert feed["unread"] == 1
    [alert] = feed["alerts"]
    assert alert["category"]["id"] == food
    assert isinstance(alert["category"]["slug"], str)
    assert alert["month"] == "2026-11"
    assert alert["threshold"] == "warning"
    assert alert["limit"] == {"amount": "1000.00", "currency": "ARS"}
    assert alert["spent"] == {"amount": "850.00", "currency": "ARS"}
    assert alert["raised_at"] == "2026-11-10T15:00:00Z"
    assert alert["read"] is False


def test_going_over_raises_the_second_alert_once(client: TestClient) -> None:
    food = _expense_category(client)
    account = _account(client)
    _budget(client, food, "1000.00")
    _spend(client, account, food, "850.00", "2026-11-05")

    _spend(client, account, food, "300.00", "2026-11-06")
    _spend(client, account, food, "10.00", "2026-11-07")
    feed = client.get("/api/alerts").json()

    assert [alert["threshold"] for alert in feed["alerts"]] in (
        ["over", "warning"],
        ["warning", "over"],
    )
    assert feed["unread"] == 2


def test_editing_an_expense_up_raises_the_alert(client: TestClient) -> None:
    food = _expense_category(client)
    account = _account(client)
    _budget(client, food, "1000.00")
    expense = _spend(client, account, food, "100.00", "2026-11-05")

    response = client.patch(
        f"/api/transactions/{expense}",
        json={
            "kind": "expense",
            "amount": "900.00",
            "category_id": food,
            "occurred_on": "2026-11-05",
        },
        headers=CSRF,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert client.get("/api/alerts").json()["unread"] == 1


def test_an_expense_of_last_month_does_not_alert(client: TestClient) -> None:
    food = _expense_category(client)
    account = _account(client)
    _budget(client, food, "1000.00")

    _spend(client, account, food, "900.00", "2026-10-30")

    assert client.get("/api/alerts").json() == {"unread": 0, "alerts": []}


def test_marking_as_read_lowers_the_count(client: TestClient) -> None:
    food = _expense_category(client)
    _budget(client, food, "1000.00")
    _spend(client, _account(client), food, "900.00", "2026-11-05")
    [alert] = client.get("/api/alerts").json()["alerts"]

    response = client.post("/api/alerts/read", json={"ids": [alert["id"]]}, headers=CSRF)
    again = client.post("/api/alerts/read", json={"ids": [alert["id"]]}, headers=CSRF)
    feed = client.get("/api/alerts").json()

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert again.status_code == status.HTTP_204_NO_CONTENT
    assert feed["unread"] == 0
    assert feed["alerts"][0]["read"] is True


@pytest.mark.parametrize(
    "body",
    [
        {"ids": []},
        {"ids": ["no-es-un-id"]},
        {"ids": [str(uuid4()) for _ in range(51)]},
        {"ids": [str(uuid4())], "all": True},
        {},
    ],
)
def test_marking_as_read_validates_the_ids(client: TestClient, body: dict[str, Any]) -> None:
    response = client.post("/api/alerts/read", json=body, headers=CSRF)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_marking_as_read_needs_the_csrf_header(client: TestClient) -> None:
    response = client.post("/api/alerts/read", json={"ids": [str(uuid4())]})

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_nobody_sees_or_reads_the_alerts_of_another_person(client: TestClient) -> None:
    food = _expense_category(client)
    _budget(client, food, "1000.00")
    _spend(client, _account(client), food, "900.00", "2026-11-05")
    [alert] = client.get("/api/alerts").json()["alerts"]
    mine = dict(client.cookies)

    _sign_in(client, "otra")
    assert client.get("/api/alerts").json() == {"unread": 0, "alerts": []}
    marked = client.post("/api/alerts/read", json={"ids": [alert["id"]]}, headers=CSRF)

    client.cookies.clear()
    client.cookies.update(mine)
    assert marked.status_code == status.HTTP_204_NO_CONTENT
    assert client.get("/api/alerts").json()["unread"] == 1


def test_a_failing_evaluation_does_not_break_the_expense(
    client: TestClient, app_parts: dict[str, Any]
) -> None:
    """El gasto ya está confirmado: un error haría que el cliente lo reintente (ADR-0022)."""
    alerts: InMemoryAlertsUnitFactory = app_parts["alerts"]
    alerts.gateways = replace(alerts.gateways, budgets=BrokenBudgets())
    food = _expense_category(client)
    _budget(client, food, "1000.00")

    _spend(client, _account(client), food, "900.00", "2026-11-05")

    assert client.get("/api/transactions").json()["items"][0]["amount"] == "900.00"
    assert client.get("/api/alerts").json()["unread"] == 0


def test_the_alerts_need_a_session(app_parts: dict[str, Any]) -> None:
    with TestClient(app_parts["app"], base_url="https://testserver") as anonymous:
        response = anonymous.get("/api/alerts")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"code": "NOT_AUTHENTICATED"}
