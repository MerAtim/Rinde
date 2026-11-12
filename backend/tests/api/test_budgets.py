"""API de presupuestos, con los otros módulos en memoria (ADR-0021)."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rinde.config import Settings
from rinde.main import create_app
from rinde.rates.domain.quote import RateSource
from rinde.shared.domain.rate_type import RateType
from tests.fakes import (
    FakeClock,
    FakeDatabaseProbe,
    InMemoryAccountsUnitFactory,
    InMemoryAuthUnitFactory,
    InMemoryBudgetsUnitFactory,
    InMemoryPreferencesUnitFactory,
    InMemoryRatesUnitFactory,
    InMemoryTransactionsUnitFactory,
)
from tests.unit.rates.fakes import FakeHistoryProvider, FakeRateProvider, quote

CSRF = {"X-Requested-With": "rinde"}
PASSPHRASE = "mi gato come fideos los martes"
# Las 12 de Buenos Aires del 10 de noviembre de 2026.
NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)
TODAY = date(2026, 11, 10)


@pytest.fixture
def clock() -> FakeClock:
    clock = FakeClock()
    clock.current = NOW
    return clock


@pytest.fixture
def client(settings: Settings, clock: FakeClock) -> Iterator[TestClient]:
    days = [date(2026, 10, 1) + timedelta(days=n) for n in range((TODAY - date(2026, 10, 1)).days)]
    rates = InMemoryRatesUnitFactory(
        FakeRateProvider(quote(RateType.MEP, TODAY, buy="2000", sell="2100")),
        FakeHistoryProvider(
            *(
                quote(RateType.MEP, day, buy="2000", sell="2100", source=RateSource.ARGENTINADATOS)
                for day in days
            )
        ),
    )
    accounts = InMemoryAccountsUnitFactory()
    transactions = InMemoryTransactionsUnitFactory(accounts.accounts, clock)
    preferences = InMemoryPreferencesUnitFactory()
    app = create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=InMemoryAuthUnitFactory(),
        accounts_factory=accounts,
        transactions_factory=transactions,
        rates_factory=rates,
        preferences_factory=preferences,
        budgets_factory=InMemoryBudgetsUnitFactory(transactions, preferences, rates, clock),
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


def _category(client: TestClient, kind: str = "expense") -> str:
    categories: list[dict[str, Any]] = client.get("/api/categories").json()
    identifier: str = next(row["id"] for row in categories if row["kind"] == kind)
    return identifier


def _spend(client: TestClient, category_id: str, amount: str, currency: str = "ARS") -> None:
    account = client.post(
        "/api/accounts",
        json={"name": f"Cuenta en {currency} {amount}", "kind": "bank", "currency": currency},
        headers=CSRF,
    ).json()["id"]
    response = client.post(
        "/api/transactions",
        json={
            "account_id": account,
            "kind": "expense",
            "amount": amount,
            "category_id": category_id,
            "occurred_on": "2026-11-05",
        },
        headers=CSRF,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text


def _set(client: TestClient, category_id: str, amount: str, currency: str = "ARS") -> Any:
    return client.put(
        f"/api/budgets/{category_id}",
        json={"amount": amount, "currency": currency},
        headers=CSRF,
    )


def _money(amount: str, currency: str = "ARS") -> dict[str, str]:
    return {"amount": amount, "currency": currency}


def test_without_budgets_the_month_is_empty(client: TestClient) -> None:
    response = client.get("/api/budgets")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"month": "2026-11", "rate_type": "mep", "budgets": []}


def test_a_budget_measures_the_spending_of_the_month(client: TestClient) -> None:
    food = _category(client)
    _spend(client, food, "200000.00")
    _spend(client, food, "20.00", "USD")

    created = _set(client, food, "300000.00")
    budgets = client.get("/api/budgets").json()["budgets"]

    assert created.status_code == status.HTTP_200_OK
    assert created.json() == {
        "category_id": food,
        "since": "2026-11",
        "limit": _money("300000.00"),
    }
    [budget] = budgets
    assert budget["category"]["id"] == food
    # Las sembradas llevan su identificador, para que la interfaz las traduzca.
    assert isinstance(budget["category"]["slug"], str)
    assert budget["since"] == "2026-11"
    assert budget["limit"] == _money("300000.00")
    # 20 dólares al MEP de venta, 2100: lo que se debe, del lado prudente.
    assert budget["spent"] == _money("242000.00")
    assert budget["remaining"] == _money("58000.00")
    assert budget["ratio"] == "0.8067"
    assert budget["status"] == "warning"
    assert budget["unconverted"] == []


def test_a_limit_in_dollars_converts_pesos_and_can_go_over(client: TestClient) -> None:
    food = _category(client)
    _spend(client, food, "105000.00")

    _set(client, food, "40.00", "USD")
    [budget] = client.get("/api/budgets").json()["budgets"]

    # 105.000 pesos al MEP de compra, 2000, son 52,50 dólares.
    assert budget["spent"] == _money("52.50", "USD")
    assert budget["remaining"] == _money("-12.50", "USD")
    assert budget["status"] == "over"


def test_setting_the_same_limit_twice_changes_nothing(client: TestClient) -> None:
    food = _category(client)

    first = _set(client, food, "300000.00")
    second = _set(client, food, "300000.00")

    assert first.json() == second.json()
    assert len(client.get("/api/budgets").json()["budgets"]) == 1


def test_a_change_keeps_the_limit_of_the_months_before(
    client: TestClient, clock: FakeClock
) -> None:
    food = _category(client)
    clock.current = NOW - timedelta(days=31)
    _set(client, food, "300000.00")
    clock.current = NOW

    _set(client, food, "350000.00")

    october = client.get("/api/budgets", params={"month": "2026-10"}).json()
    november = client.get("/api/budgets").json()
    assert october["budgets"][0]["limit"] == _money("300000.00")
    assert october["budgets"][0]["since"] == "2026-10"
    assert november["budgets"][0]["limit"] == _money("350000.00")


def test_removing_keeps_the_past_and_a_second_removal_is_not_found(
    client: TestClient, clock: FakeClock
) -> None:
    food = _category(client)
    clock.current = NOW - timedelta(days=31)
    _set(client, food, "300000.00")
    clock.current = NOW

    removed = client.delete(f"/api/budgets/{food}", headers=CSRF)
    again = client.delete(f"/api/budgets/{food}", headers=CSRF)

    assert removed.status_code == status.HTTP_204_NO_CONTENT
    assert client.get("/api/budgets").json()["budgets"] == []
    assert len(client.get("/api/budgets", params={"month": "2026-10"}).json()["budgets"]) == 1
    assert again.status_code == status.HTTP_404_NOT_FOUND
    assert again.json() == {"code": "BUDGET_NOT_FOUND"}


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"amount": "0.00", "currency": "ARS"}, "BUDGET_AMOUNT_INVALID"),
        ({"amount": "-10.00", "currency": "ARS"}, "BUDGET_AMOUNT_INVALID"),
        ({"amount": "0.10000000", "currency": "BTC"}, "BUDGET_CURRENCY_NOT_ALLOWED"),
        ({"amount": "10.001", "currency": "ARS"}, "AMOUNT_TOO_PRECISE"),
    ],
)
def test_rejects_an_invalid_limit_with_a_stable_code(
    client: TestClient, body: dict[str, str], code: str
) -> None:
    response = client.put(f"/api/budgets/{_category(client)}", json=body, headers=CSRF)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {"code": code}


@pytest.mark.parametrize(
    "body",
    [
        {"amount": 1000, "currency": "ARS"},
        {"amount": "1000.00"},
        {"amount": "1000.00", "currency": "ARS", "since": "2026-01"},
    ],
)
def test_validates_the_body_at_the_edge(client: TestClient, body: dict[str, Any]) -> None:
    response = client.put(f"/api/budgets/{_category(client)}", json=body, headers=CSRF)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_an_income_category_is_not_budgeted(client: TestClient) -> None:
    response = _set(client, _category(client, "income"), "1000.00")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {"code": "BUDGET_CATEGORY_NOT_EXPENSE"}


def test_an_unknown_category_is_not_found(client: TestClient) -> None:
    response = _set(client, "00000000-0000-4000-8000-000000000000", "1000.00")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"code": "BUDGET_CATEGORY_NOT_FOUND"}


@pytest.mark.parametrize("month", ["2026-12", "2027-01"])
def test_a_month_that_has_not_started_is_invalid(client: TestClient, month: str) -> None:
    response = client.get("/api/budgets", params={"month": month})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {"code": "BUDGET_MONTH_INVALID"}


@pytest.mark.parametrize("month", ["2026-13", "2026-1", "noviembre"])
def test_a_malformed_month_is_rejected(client: TestClient, month: str) -> None:
    response = client.get("/api/budgets", params={"month": month})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_someone_else_neither_sees_nor_touches_my_budgets(client: TestClient) -> None:
    food = _category(client)
    _set(client, food, "300000.00")

    _sign_in(client, "intrusa")
    seen = client.get("/api/budgets").json()["budgets"]
    changed = _set(client, food, "1.00")
    removed = client.delete(f"/api/budgets/{food}", headers=CSRF)

    assert seen == []
    assert changed.status_code == status.HTTP_404_NOT_FOUND
    assert removed.status_code == status.HTTP_404_NOT_FOUND
