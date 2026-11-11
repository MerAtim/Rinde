"""API del dashboard, con los otros módulos en memoria (ADR-0018)."""

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
    InMemoryPreferencesUnitFactory,
    InMemoryRatesUnitFactory,
    InMemoryTransactionsUnitFactory,
)
from tests.unit.rates.fakes import FakeHistoryProvider, FakeRateProvider, quote

CSRF = {"X-Requested-With": "rinde"}
PASSPHRASE = "mi gato come fideos los martes"
# Las 12 de Buenos Aires del 10 de noviembre de 2026, el mismo momento que cotizaciones.
NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)
TODAY = date(2026, 11, 10)
PERIOD = {"from": "2026-09", "to": "2026-11"}


def _history() -> FakeHistoryProvider:
    """MEP a 1000/1100 en septiembre y a 2000/2100 desde octubre, todos los días."""
    days = [date(2026, 8, 20) + timedelta(days=n) for n in range((TODAY - date(2026, 8, 20)).days)]
    return FakeHistoryProvider(
        *(
            quote(
                RateType.MEP,
                day,
                buy="1000" if day.month < 10 else "2000",
                sell="1100" if day.month < 10 else "2100",
                source=RateSource.ARGENTINADATOS,
            )
            for day in days
        )
    )


@pytest.fixture
def rates() -> InMemoryRatesUnitFactory:
    live = quote(RateType.MEP, TODAY, buy="2000", sell="2100")
    return InMemoryRatesUnitFactory(FakeRateProvider(live), _history())


@pytest.fixture
def client(settings: Settings, rates: InMemoryRatesUnitFactory) -> Iterator[TestClient]:
    accounts = InMemoryAccountsUnitFactory()
    clock = FakeClock()
    clock.current = NOW
    app = create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=InMemoryAuthUnitFactory(),
        accounts_factory=accounts,
        transactions_factory=InMemoryTransactionsUnitFactory(accounts.accounts, clock),
        rates_factory=rates,
        preferences_factory=InMemoryPreferencesUnitFactory(),
        dashboard_clock=clock,
    )
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def _sign_in(client: TestClient, username: str) -> None:
    client.cookies.clear()
    response = client.post(
        "/api/auth/register", json={"username": username, "password": PASSPHRASE}, headers=CSRF
    )
    assert response.status_code == status.HTTP_201_CREATED


def _account(client: TestClient, currency: str) -> str:
    response = client.post(
        "/api/accounts",
        json={
            "name": f"Cuenta en {currency}",
            "kind": "crypto_wallet" if currency == "BTC" else "bank",
            "currency": currency,
        },
        headers=CSRF,
    )
    identifier: str = response.json()["id"]
    return identifier


def _category(client: TestClient, kind: str) -> dict[str, Any]:
    categories: list[dict[str, Any]] = client.get("/api/categories").json()
    return next(row for row in categories if row["kind"] == kind)


def _move(client: TestClient, account_id: str, kind: str, amount: str, day: str) -> None:
    response = client.post(
        "/api/transactions",
        json={
            "account_id": account_id,
            "kind": kind,
            "amount": amount,
            "category_id": _category(client, kind)["id"],
            "occurred_on": day,
        },
        headers=CSRF,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text


def _money(amount: str, currency: str = "ARS") -> dict[str, str]:
    return {"amount": amount, "currency": currency}


def test_a_new_person_sees_six_empty_months_in_pesos_at_the_mep(client: TestClient) -> None:
    _sign_in(client, "mechi")

    response = client.get("/api/dashboard")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["period"] == {
        "first": "2026-06",
        "last": "2026-11",
        "since": "2026-06-01",
        "until": "2026-11-10",
    }
    assert body["reference"] == {"currency": "ARS", "rate_type": "mep"}
    assert [m["month"] for m in body["monthly"]] == [f"2026-{m:02d}" for m in range(6, 12)]
    assert body["spending"] == []
    assert body["unconverted"] == []
    assert body["net_worth"][-1] == {
        "month": "2026-11",
        "on": "2026-11-10",
        "total": _money("0.00"),
    }


def test_each_amount_is_converted_with_the_dollar_of_its_day(client: TestClient) -> None:
    _sign_in(client, "mechi")
    pesos, dollars = _account(client, "ARS"), _account(client, "USD")
    _move(client, pesos, "income", "500000.00", "2026-09-01")
    _move(client, pesos, "expense", "1000.00", "2026-09-02")
    _move(client, dollars, "income", "10.00", "2026-09-03")
    _move(client, dollars, "expense", "1.00", "2026-10-05")

    body = client.get("/api/dashboard", params=PERIOD).json()

    september, october, november = body["monthly"]
    # Diez dólares que entran, a la compra de septiembre.
    assert september["income"] == _money("510000.00")
    assert september["expense"] == _money("1000.00")
    # Un dólar que sale, a la venta de octubre.
    assert october["expense"] == _money("2100.00")
    assert november["net"] == _money("0.00")
    # Nueve dólares que se tienen, a la compra de cada cierre.
    assert [p["total"]["amount"] for p in body["net_worth"]] == [
        "509000.00",
        "517000.00",
        "517000.00",
    ]
    assert [s["total"] for s in body["spending"]] == [_money("3100.00")]
    assert body["spending"][0]["category"]["slug"] == _category(client, "expense")["slug"]


def test_totals_in_dollars_follow_the_preferences(client: TestClient) -> None:
    _sign_in(client, "mechi")
    pesos = _account(client, "ARS")
    _move(client, pesos, "income", "1100.00", "2026-09-01")
    client.put(
        "/api/preferences", json={"reference_currency": "USD", "rate_type": "mep"}, headers=CSRF
    )

    body = client.get("/api/dashboard", params=PERIOD).json()

    assert body["reference"]["currency"] == "USD"
    # Pesos que entran compran dólares a la venta: 1100 / 1100.
    assert body["monthly"][0]["income"] == _money("1.00", "USD")
    # Hoy el MEP vende a 2100.
    assert body["net_worth"][-1]["total"] == _money("0.52", "USD")


def test_bitcoin_is_reported_apart_and_not_mixed_in(client: TestClient) -> None:
    _sign_in(client, "mechi")
    wallet = _account(client, "BTC")
    _move(client, wallet, "income", "0.01000000", "2026-09-04")

    body = client.get("/api/dashboard", params=PERIOD).json()

    assert body["monthly"][0]["income"] == _money("0.00")
    assert body["net_worth"][-1]["total"] == _money("0.00")
    assert body["unconverted"] == [
        {
            "currency": "BTC",
            "income": _money("0.01000000", "BTC"),
            "expense": _money("0.00000000", "BTC"),
            "balance": _money("0.01000000", "BTC"),
        }
    ]


def test_choosing_accounts_narrows_everything(client: TestClient) -> None:
    _sign_in(client, "mechi")
    one, other = _account(client, "ARS"), _account(client, "ARS")
    _move(client, one, "income", "100.00", "2026-09-01")
    _move(client, other, "income", "900.00", "2026-09-01")

    body = client.get("/api/dashboard", params={**PERIOD, "account": [one]}).json()

    assert body["monthly"][0]["income"] == _money("100.00")
    assert body["net_worth"][-1]["total"] == _money("100.00")


def test_someone_elses_account_in_the_filter_shows_nothing_of_theirs(client: TestClient) -> None:
    _sign_in(client, "mechi")
    theirs = _account(client, "ARS")
    _move(client, theirs, "income", "100.00", "2026-09-01")
    _sign_in(client, "intrusa")

    body = client.get("/api/dashboard", params={**PERIOD, "account": [theirs]}).json()

    assert body["monthly"][0]["income"] == _money("0.00")
    assert body["net_worth"][-1]["total"] == _money("0.00")
    assert body["spending"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"from": "2026-13"},
        {"from": "2026-9"},
        {"to": "2026-12"},
        {"from": "2026-10", "to": "2026-09"},
        {"from": "2024-01"},
        {"account": "no-es-un-id"},
        {"desde": "2026-09"},
    ],
)
def test_a_wrong_period_is_rejected_with_a_stable_code(
    client: TestClient, params: dict[str, str]
) -> None:
    _sign_in(client, "mechi")

    response = client.get("/api/dashboard", params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    if "code" in response.json():
        assert response.json() == {"code": "DASHBOARD_PERIOD_INVALID"}


def test_without_a_session_there_is_no_dashboard(client: TestClient) -> None:
    assert client.get("/api/dashboard").status_code == status.HTTP_401_UNAUTHORIZED
