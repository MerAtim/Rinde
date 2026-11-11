"""Objetivo medible de la fase 4: p95 < 300 ms del dashboard con 50.000 movimientos (ADR-0018).

Se mide de punta a punta: la aplicación completa, con su sesión real, su base
real y sus casos de uso, a través de HTTP en memoria. Lo único que no participa
es la red: el histórico de cotizaciones ya está guardado, que es la condición
que fija el ADR (la primera carga de una serie depende de una fuente externa y
no es lo que se mide).

El período es el de los seis meses cerrados anteriores al actual, para que no
haga falta la cotización de hoy, que sale de la red. Los datos se siembran con
una semilla fija, así cada corrida mide lo mismo, y se borran al terminar.
"""

import random
import statistics
import time
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from rinde.accounts.infrastructure.tables import accounts
from rinde.auth.application.dependencies import AuthServices
from rinde.auth.infrastructure.argon2_hasher import Argon2PasswordHasher
from rinde.auth.infrastructure.factory import SqlAlchemyAuthUnitFactory
from rinde.auth.infrastructure.system import SecureRandomSecrets
from rinde.auth.infrastructure.tables import users
from rinde.config import Settings
from rinde.main import create_app
from rinde.rates.application.ports import QuoteRequest, RateSourceUnavailableError
from rinde.rates.domain.quote import Quote
from rinde.rates.infrastructure.factory import SqlAlchemyRatesUnitFactory
from rinde.rates.infrastructure.tables import exchange_rates
from rinde.shared.domain.calendar import argentine_day
from rinde.shared.domain.rate_type import RateType
from rinde.shared.infrastructure.clock import SystemClock
from rinde.transactions.infrastructure.tables import categories, transactions, transfers
from tests.fakes import FakeBreachChecker

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

TRANSACTIONS = 50_000
TRANSFERS = 2_000
HISTORY_DAYS = 730
WARMUP = 5
SAMPLES = 60
P95_LIMIT_MS = 300.0
CSRF = {"X-Requested-With": "rinde"}
PASSPHRASE = "mi gato come fideos los martes"
# Marca las cotizaciones sembradas, para borrar solo esas al terminar.
SEEDED_AT = datetime(1999, 1, 1, tzinfo=UTC)


class _NoNetwork:
    """Si el dashboard saliera a la red, la medición no sería la que pide el ADR."""

    def __init__(self) -> None:
        self.calls = 0

    async def quotes(self, request: QuoteRequest) -> dict[RateType, Quote]:
        self.calls += 1
        raise RateSourceUnavailableError

    async def series(self, rate_type: RateType) -> list[Quote]:
        self.calls += 1
        raise RateSourceUnavailableError


def _month_shift(month: date, months: int) -> date:
    index = month.year * 12 + month.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


async def _seed(engine: AsyncEngine, owner_id: UUID, today: date, since: date) -> None:
    rng = random.Random(20261111)  # noqa: S311  (datos de prueba, no secretos)
    now = datetime.now(UTC)
    account_rows = [
        {"id": uuid4(), "currency": currency, "kind": "bank"}
        for currency in ("ARS", "ARS", "ARS", "ARS", "USD", "USD")
    ]
    category_rows = [
        {"id": uuid4(), "kind": "expense" if n < 15 else "income", "name": f"Categoría {n}"}
        for n in range(20)
    ]
    async with engine.begin() as connection:
        await connection.execute(
            insert(accounts),
            [
                {**row, "owner_id": owner_id, "name": f"Cuenta {n}", "created_at": now}
                for n, row in enumerate(account_rows)
            ],
        )
        await connection.execute(
            insert(categories),
            [{**row, "owner_id": owner_id, "created_at": now} for row in category_rows],
        )
        rows = []
        for _ in range(TRANSACTIONS):
            account = rng.choice(account_rows)
            category = rng.choice(category_rows)
            cents = rng.randint(100, 5_000_000 if account["currency"] == "ARS" else 50_000)
            rows.append(
                {
                    "id": uuid4(),
                    "owner_id": owner_id,
                    "account_id": account["id"],
                    "currency": account["currency"],
                    "kind": category["kind"],
                    "amount": Decimal(cents).scaleb(-2),
                    "category_id": category["id"],
                    "occurred_on": today - timedelta(days=rng.randrange(HISTORY_DAYS)),
                    "created_at": now,
                    "updated_at": now,
                }
            )
        for start in range(0, len(rows), 5_000):
            await connection.execute(insert(transactions), rows[start : start + 5_000])
        transfer_rows = []
        for _ in range(TRANSFERS):
            origin, destination = rng.sample(account_rows, 2)
            amount = Decimal(rng.randint(100, 100_000)).scaleb(-2)
            transfer_rows.append(
                {
                    "id": uuid4(),
                    "owner_id": owner_id,
                    "from_account_id": origin["id"],
                    "currency_out": origin["currency"],
                    "amount_out": amount,
                    "to_account_id": destination["id"],
                    "currency_in": destination["currency"],
                    "amount_in": amount,
                    "occurred_on": today - timedelta(days=rng.randrange(HISTORY_DAYS)),
                    "created_at": now,
                    "updated_at": now,
                }
            )
        await connection.execute(insert(transfers), transfer_rows)
        # El histórico ya cargado: un MEP por día, desde antes del período.
        day = since - timedelta(days=14)
        quote_rows = []
        while day < today:
            buy = Decimal(1000 + (day - since).days)
            quote_rows.append(
                {
                    "day": day,
                    "base": "USD",
                    "counter": "ARS",
                    "rate_type": "mep",
                    "source": "argentinadatos",
                    "buy": buy,
                    "sell": buy + 20,
                    "updated_at": None,
                    "fetched_at": SEEDED_AT,
                }
            )
            day += timedelta(days=1)
        await connection.execute(pg_insert(exchange_rates).on_conflict_do_nothing(), quote_rows)
        await connection.exec_driver_sql("ANALYZE transactions, transfers, exchange_rates")


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


async def test_the_dashboard_answers_under_300_ms_at_p95(
    database_url: str, engine: AsyncEngine
) -> None:
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    clock = SystemClock()
    no_network = _NoNetwork()
    settings = Settings(environment="test", database_url=SecretStr(database_url))
    app = create_app(
        settings,
        # Contraseñas reales con Argon2, pero sin consultar filtraciones por la red.
        auth_factory=SqlAlchemyAuthUnitFactory(
            sessionmaker,
            AuthServices(
                hasher=Argon2PasswordHasher(),
                breaches=FakeBreachChecker(),
                clock=clock,
                secrets=SecureRandomSecrets(),
                session_ttl=timedelta(days=1),
            ),
        ),
        rates_factory=SqlAlchemyRatesUnitFactory(sessionmaker, no_network, no_network, clock),
    )
    today = argentine_day(datetime.now(UTC))
    last = _month_shift(today.replace(day=1), -1)
    first = _month_shift(last, -5)
    username = f"medicion_{uuid4().hex[:12]}"
    params = {"from": f"{first:%Y-%m}", "to": f"{last:%Y-%m}"}

    # El registro tiene un límite por dirección que se guarda en la base: una
    # dirección distinta en cada corrida (del rango para documentación, RFC
    # 5737) evita chocar con corridas anteriores sin tocar la protección.
    client_address = f"198.51.100.{uuid4().int % 254 + 1}"
    transport = httpx.ASGITransport(app=app, client=(client_address, 50000))
    # El transporte en memoria no corre el ciclo de vida: sin esto, la conexión
    # de la aplicación quedaría abierta al terminar.
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="https://testserver") as client,
    ):
        response = await client.post(
            "/api/auth/register",
            json={"username": username, "password": PASSPHRASE},
            headers=CSRF,
        )
        assert response.status_code == httpx.codes.CREATED, response.text
        async with engine.connect() as connection:
            owner_id = (
                await connection.execute(select(users.c.id).where(users.c.username == username))
            ).scalar_one()
        try:
            await _seed(engine, owner_id, today, first)

            durations = []
            for attempt in range(WARMUP + SAMPLES):
                started = time.perf_counter()
                response = await client.get("/api/dashboard", params=params)
                elapsed = (time.perf_counter() - started) * 1000
                assert response.status_code == httpx.codes.OK, response.text
                if attempt >= WARMUP:
                    durations.append(elapsed)

            body = response.json()
            p95 = statistics.quantiles(durations, n=20)[18]
            summary = (
                f"p50 {statistics.median(durations):.1f} ms, p95 {p95:.1f} ms, "
                f"máximo {max(durations):.1f} ms, en {SAMPLES} pedidos"
            )
            print(f"\nDashboard con {TRANSACTIONS} movimientos: {summary}")  # noqa: T201
            # Que mida lo que dice medir: hay datos, se convirtió y no hubo red.
            assert body["spending"], "el período quedó sin gastos: la siembra no es la esperada"
            assert all(point["total"] is not None for point in body["net_worth"])
            assert no_network.calls == 0
            assert p95 < P95_LIMIT_MS, summary
        finally:
            async with engine.begin() as connection:
                await connection.execute(delete(users).where(users.c.id == owner_id))
                await connection.execute(
                    delete(exchange_rates).where(exchange_rates.c.fetched_at == SEEDED_AT)
                )
