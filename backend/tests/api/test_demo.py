"""Cuenta demo, de punta a punta: se crea, se siembra por los otros módulos y vence (ADR-0028)."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rinde.auth.application import demo as demo_module
from rinde.auth.application.demo import DEMO_TTL
from rinde.config import Settings
from rinde.demo.application.seed import SeedDemo
from rinde.demo.infrastructure.writer import ModulesDemoWriter
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
COOKIE = "__Host-rinde_session"
# Las 9 de Buenos Aires del 11 de noviembre de 2026: el mes en curso va por la mitad.
NOW = datetime(2026, 11, 11, 12, tzinfo=UTC)


@pytest.fixture
def parts(settings: Settings) -> dict[str, Any]:
    clock = FakeClock()
    clock.current = NOW
    bus = InProcessEventBus()
    accounts = InMemoryAccountsUnitFactory(clock)
    transactions = InMemoryTransactionsUnitFactory(accounts.accounts, clock, events=bus)
    preferences = InMemoryPreferencesUnitFactory()
    rates = InMemoryRatesUnitFactory()
    budgets = InMemoryBudgetsUnitFactory(transactions, preferences, rates, clock)
    alerts = InMemoryAlertsUnitFactory(transactions, budgets, clock)
    # El sembrador real, sobre los mismos módulos que usan los endpoints.
    auth = InMemoryAuthUnitFactory(
        seeder=SeedDemo(ModulesDemoWriter(accounts, transactions, budgets), clock), clock=clock
    )
    app = create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=auth,
        accounts_factory=accounts,
        transactions_factory=transactions,
        rates_factory=rates,
        preferences_factory=preferences,
        budgets_factory=budgets,
        alerts_factory=alerts,
        event_bus=bus,
    )
    return {"app": app, "clock": clock, "auth": auth}


@pytest.fixture
def client(parts: dict[str, Any]) -> Iterator[TestClient]:
    with TestClient(parts["app"], base_url="https://testserver") as test_client:
        yield test_client


def _start(client: TestClient, origin: str = "203.0.113.7") -> Any:
    client.cookies.clear()
    return client.post("/api/auth/demo", headers={**CSRF, "CF-Connecting-IP": origin})


def test_a_demo_opens_a_session_that_lasts_as_long_as_the_demo(client: TestClient) -> None:
    response = _start(client)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["username"].startswith("demo-")
    assert body["demo_expires_at"] == "2026-11-11T14:00:00Z"
    cookie = response.headers["set-cookie"].lower()
    for attribute in (
        f"{COOKIE.lower()}=",
        f"max-age={int(DEMO_TTL.total_seconds())}",
        "httponly",
        "secure",
        "samesite=strict",
    ):
        assert attribute in cookie
    assert client.get("/api/auth/me").json() == body


def test_a_demo_comes_with_three_months_of_data_an_alert_and_nothing_in_the_future(
    client: TestClient,
) -> None:
    _start(client)

    accounts = client.get("/api/accounts").json()
    history = client.get("/api/history", params={"limit": 100}).json()["items"]
    budgets = client.get("/api/budgets").json()["budgets"]
    alerts = client.get("/api/alerts").json()["alerts"]

    assert sorted(account["currency"] for account in accounts) == ["ARS", "ARS", "ARS", "USD"]
    # Cada entrada dice si es un movimiento o una transferencia, y lo trae adentro.
    dates = [item[item["type"]]["occurred_on"] for item in history]
    assert len(dates) > 50
    assert max(dates) <= "2026-11-11"
    assert min(dates) >= "2026-09-01"
    assert len(client.get("/api/recurring").json()) == 2
    assert len(client.get("/api/installments").json()) == 1
    assert len(budgets) == 3
    # El súper del mes pasa el 80 % de su tope: la demo muestra una alerta.
    assert alerts


def test_each_visit_gets_its_own_demo(client: TestClient) -> None:
    _start(client, "203.0.113.7")
    first = {account["id"] for account in client.get("/api/accounts").json()}
    _start(client, "198.51.100.4")
    second = {account["id"] for account in client.get("/api/accounts").json()}

    assert len(first) == len(second) == 4
    assert first.isdisjoint(second)


def test_the_demo_session_ends_when_the_demo_expires(
    client: TestClient, parts: dict[str, Any]
) -> None:
    _start(client)
    parts["clock"].advance(DEMO_TTL)

    assert client.get("/api/accounts").status_code == status.HTTP_401_UNAUTHORIZED


def test_one_origin_gets_a_few_demos_per_hour(client: TestClient) -> None:
    for _ in range(3):
        assert _start(client).status_code == status.HTTP_201_CREATED

    blocked = _start(client)

    assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert blocked.json() == {"code": "TOO_MANY_ATTEMPTS"}


def test_a_full_service_answers_503_with_retry_after(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(demo_module, "MAX_DEMOS", 1)
    assert _start(client, "203.0.113.7").status_code == status.HTTP_201_CREATED

    full = _start(client, "198.51.100.4")

    assert full.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert full.json() == {"code": "DEMO_UNAVAILABLE"}
    assert full.headers["retry-after"] == str(int(DEMO_TTL.total_seconds()))


def test_creating_a_demo_requires_the_csrf_header(client: TestClient) -> None:
    response = client.post("/api/auth/demo")

    assert response.status_code == status.HTTP_403_FORBIDDEN
