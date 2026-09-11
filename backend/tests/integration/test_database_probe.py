import os

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from rinde.health.infrastructure.database_probe import SqlAlchemyDatabaseProbe

pytestmark = pytest.mark.anyio


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("RINDE_DATABASE_URL")
    if url is None:
        if os.environ.get("CI"):
            pytest.fail("En CI los tests de integración requieren RINDE_DATABASE_URL")
        pytest.skip("RINDE_DATABASE_URL no está definida: se omite el test contra PostgreSQL")
    return url


@pytest.mark.integration
async def test_reachable_with_real_database(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        assert await SqlAlchemyDatabaseProbe(engine).is_reachable()
    finally:
        await engine.dispose()


async def test_unreachable_when_nothing_listens() -> None:
    engine = create_async_engine("postgresql+psycopg://nadie:nada@127.0.0.1:1/nada")
    try:
        assert not await SqlAlchemyDatabaseProbe(engine, timeout_seconds=2).is_reachable()
    finally:
        await engine.dispose()
