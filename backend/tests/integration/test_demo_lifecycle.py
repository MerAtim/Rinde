"""La demo completa contra PostgreSQL real: siembra, tamaño y borrado (ADR-0028).

Se mide cuánto ocupa una demo, que es lo que sostiene el tope de 100, y se
comprueba que al vencer se va con todo lo suyo, auditoría incluida. La red no
participa: las cotizaciones fallan a propósito, como si la fuente estuviera caída.
"""

import time
from collections.abc import AsyncIterator
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import Table, delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from rinde.auth.infrastructure.tables import sessions, users
from rinde.config import Settings
from rinde.main import create_app
from rinde.rates.application.ports import QuoteRequest, RateSourceUnavailableError
from rinde.rates.domain.quote import Quote
from rinde.rates.infrastructure.factory import SqlAlchemyRatesUnitFactory
from rinde.shared.domain.rate_type import RateType
from rinde.shared.infrastructure.clock import SystemClock
from rinde.shared.infrastructure.database import metadata
from tests.integration.test_dashboard_performance import _publish

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

CSRF = {"X-Requested-With": "rinde"}
# Lo que el ADR supone por demo, datos e índices; acá se mide solo el dato.
MAX_DATA_BYTES = 100_000


class _NoNetwork:
    async def quotes(self, request: QuoteRequest) -> dict[RateType, Quote]:
        raise RateSourceUnavailableError

    async def series(self, rate_type: RateType) -> list[Quote]:
        raise RateSourceUnavailableError


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


def _owned_tables() -> list[Table]:
    """Todas las tablas con datos de una persona: las que tienen `owner_id`."""
    return [table for table in metadata.sorted_tables if "owner_id" in table.c]


async def _bytes_and_rows(engine: AsyncEngine, owner_id: UUID) -> tuple[int, int]:
    total_bytes = total_rows = 0
    async with engine.connect() as connection:
        for table in _owned_tables():
            row = (
                await connection.execute(
                    select(
                        func.coalesce(func.sum(func.pg_column_size(text(table.name))), 0),
                        func.count(),
                    )
                    .select_from(table)
                    .where(table.c.owner_id == owner_id)
                )
            ).one()
            total_bytes += int(row[0])
            total_rows += int(row[1])
    return total_bytes, total_rows


async def _demo_id(engine: AsyncEngine, username: str) -> UUID:
    async with engine.connect() as connection:
        found = await connection.execute(select(users.c.id).where(users.c.username == username))
        return UUID(str(found.scalar_one()))


async def test_a_demo_is_small_and_leaves_with_everything_when_it_expires(
    database_url: str, engine: AsyncEngine
) -> None:
    clock = SystemClock()
    no_network = _NoNetwork()
    app = create_app(
        Settings(environment="test", database_url=SecretStr(database_url)),
        rates_factory=SqlAlchemyRatesUnitFactory(
            async_sessionmaker(engine, expire_on_commit=False), no_network, no_network, clock
        ),
    )
    # Una dirección distinta en cada corrida (RFC 5737): el límite por origen
    # queda guardado en la base entre corridas.
    origin = f"192.0.2.{uuid4().int % 254 + 1}"
    transport = httpx.ASGITransport(app=app, client=(origin, 50000))
    created: list[UUID] = []
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="https://testserver") as client,
    ):
        try:
            started = time.perf_counter()
            response = await client.post("/api/auth/demo", headers=CSRF)
            elapsed = time.perf_counter() - started
            assert response.status_code == httpx.codes.CREATED, response.text
            old = await _demo_id(engine, response.json()["username"])
            created.append(old)

            size, rows = await _bytes_and_rows(engine, old)
            summary = f"{rows} filas, {size / 1000:.1f} kB de datos, creada en {elapsed:.2f} s"
            print(f"\nDemo: {summary}")  # noqa: T201
            _publish(f"Demo: {summary}")
            assert rows > 100
            assert size < MAX_DATA_BYTES, summary

            # Se la hace vencer, y la próxima demo la borra al crearse.
            async with engine.begin() as connection:
                await connection.execute(
                    update(users)
                    .where(users.c.id == old)
                    .values(
                        created_at=users.c.created_at - timedelta(hours=3),
                        demo_expires_at=users.c.created_at - timedelta(hours=1),
                    )
                )
            client.cookies.clear()
            again = await client.post("/api/auth/demo", headers=CSRF)
            assert again.status_code == httpx.codes.CREATED, again.text
            created.append(await _demo_id(engine, again.json()["username"]))

            assert await _bytes_and_rows(engine, old) == (0, 0)
            async with engine.connect() as connection:
                left = await connection.execute(
                    select(func.count()).select_from(sessions).where(sessions.c.user_id == old)
                )
                assert left.scalar_one() == 0
        finally:
            async with engine.begin() as connection:
                await connection.execute(delete(users).where(users.c.id.in_(created)))
