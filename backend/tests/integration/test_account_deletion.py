"""Borrar la cuenta contra PostgreSQL real: se va con todo lo suyo (ADR-0034).

Se siembra una cuenta con los datos de una demo, que tocan casi todas las
tablas, y se la convierte en una cuenta común con contraseña. Al borrarla, no
puede quedar ni una fila suya en ninguna tabla que apunte a `users`, aunque la
tabla sea nueva: la lista sale de las claves foráneas, no de una lista a mano.
Otra cuenta sembrada igual queda intacta.
"""

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import Column, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from rinde.auth.domain.password_policy import normalize_password
from rinde.auth.infrastructure.argon2_hasher import Argon2PasswordHasher
from rinde.auth.infrastructure.tables import account_deletions, users
from rinde.config import Settings
from rinde.main import create_app
from rinde.rates.infrastructure.factory import SqlAlchemyRatesUnitFactory
from rinde.shared.infrastructure.clock import SystemClock
from rinde.shared.infrastructure.database import metadata
from tests.integration.test_demo_lifecycle import _NoNetwork

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

CSRF = {"X-Requested-With": "rinde"}
PASSPHRASE = "mi gato come fideos los martes"


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


def _columns_pointing_to_users() -> list[Column[UUID]]:
    return [
        key.parent
        for table in metadata.sorted_tables
        for key in table.foreign_keys
        if key.column.table is users
    ]


async def _rows_by_table(engine: AsyncEngine, user_id: UUID) -> dict[str, int]:
    rows: dict[str, int] = {}
    async with engine.connect() as connection:
        for column in _columns_pointing_to_users():
            found = await connection.execute(
                select(func.count()).select_from(column.table).where(column == user_id)
            )
            name = f"{column.table.name}.{column.name}"
            rows[name] = int(found.scalar_one())
    return rows


async def _user_id(engine: AsyncEngine, username: str) -> UUID:
    async with engine.connect() as connection:
        found = await connection.execute(select(users.c.id).where(users.c.username == username))
        return UUID(str(found.scalar_one()))


async def test_deleting_an_account_leaves_no_row_of_it_and_keeps_the_others(
    database_url: str, engine: AsyncEngine
) -> None:
    no_network = _NoNetwork()
    app = create_app(
        Settings(environment="test", database_url=SecretStr(database_url)),
        rates_factory=SqlAlchemyRatesUnitFactory(
            async_sessionmaker(engine, expire_on_commit=False),
            no_network,
            no_network,
            SystemClock(),
        ),
    )
    origin = f"192.0.2.{uuid4().int % 254 + 1}"
    transport = httpx.ASGITransport(app=app, client=(origin, 50000))
    created: list[UUID] = []
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="https://testserver") as client,
    ):
        try:
            kept = await client.post("/api/auth/demo", headers=CSRF)
            assert kept.status_code == httpx.codes.CREATED, kept.text
            other = await _user_id(engine, kept.json()["username"])
            created.append(other)

            client.cookies.clear()
            seeded = await client.post("/api/auth/demo", headers=CSRF)
            assert seeded.status_code == httpx.codes.CREATED, seeded.text
            target = await _user_id(engine, seeded.json()["username"])
            created.append(target)
            # Una demo no se puede borrar a mano: se la vuelve una cuenta común.
            password_hash = await Argon2PasswordHasher().hash(normalize_password(PASSPHRASE))
            async with engine.begin() as connection:
                await connection.execute(
                    update(users)
                    .where(users.c.id == target)
                    .values(
                        username=f"borrar-{uuid4().hex[:8]}",
                        demo_expires_at=None,
                        password_hash=password_hash,
                    )
                )
            before = await _rows_by_table(engine, target)
            assert sum(before.values()) > 100, before

            response = await client.post(
                "/api/auth/me/delete", json={"password": PASSPHRASE}, headers=CSRF
            )

            assert response.status_code == httpx.codes.NO_CONTENT, response.text
            assert await _rows_by_table(engine, target) == dict.fromkeys(before, 0)
            assert await _rows_by_table(engine, other) == before
            async with engine.connect() as connection:
                recorded = await connection.execute(
                    select(func.count())
                    .select_from(account_deletions)
                    .where(account_deletions.c.user_id == target)
                )
                assert recorded.scalar_one() == 1
        finally:
            async with engine.begin() as connection:
                await connection.execute(delete(users).where(users.c.id.in_(created)))
                await connection.execute(
                    delete(account_deletions).where(account_deletions.c.user_id.in_(created))
                )
