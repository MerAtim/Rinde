"""Repositorio del IPC contra PostgreSQL real. Cada test se deshace al terminar."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from rinde.inflation.infrastructure.repositories import SqlAlchemyCpiRepository
from rinde.inflation.infrastructure.tables import cpi_months
from tests.unit.inflation.fakes import cpi

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

FETCHED_AT = datetime(2026, 11, 14, 15, tzinfo=UTC)
SEPT, OCT = date(2026, 9, 1), date(2026, 10, 1)


@pytest.fixture
async def session(database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        db_session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield db_session
        finally:
            await db_session.close()
            await transaction.rollback()
    await engine.dispose()


async def test_the_months_come_back_exact_and_in_order(session: AsyncSession) -> None:
    repository = SqlAlchemyCpiRepository(session)
    await repository.add_all([cpi(OCT, "12785.9321"), cpi(SEPT, "12514.1508")], FETCHED_AT)

    months = await repository.for_range(SEPT, OCT)

    assert months == [cpi(SEPT, "12514.1508"), cpi(OCT, "12785.9321")]
    assert months[1].index == Decimal("12785.9321")
    assert await repository.for_range(date(2026, 11, 1), date(2026, 12, 1)) == []


async def test_the_latest_is_the_newest_month(session: AsyncSession) -> None:
    repository = SqlAlchemyCpiRepository(session)
    assert await repository.latest() is None

    await repository.add_all([cpi(SEPT, "1"), cpi(OCT, "2")], FETCHED_AT)

    assert await repository.latest() == cpi(OCT, "2")


async def test_a_stored_month_is_never_overwritten(session: AsyncSession) -> None:
    repository = SqlAlchemyCpiRepository(session)
    await repository.add_all([cpi(OCT, "1")], FETCHED_AT)

    await repository.add_all([cpi(OCT, "2")], FETCHED_AT)
    await repository.add_all([], FETCHED_AT)

    assert await repository.for_range(OCT, OCT) == [cpi(OCT, "1")]


@pytest.mark.parametrize(
    "row",
    [
        {"month": date(2026, 10, 2), "value": Decimal(1), "source": "indec"},
        {"month": OCT, "value": Decimal(0), "source": "indec"},
        {"month": OCT, "value": Decimal(1), "source": "otra"},
    ],
    ids=["mitad de mes", "cero", "fuente desconocida"],
)
async def test_the_database_rejects_what_the_domain_rejects(
    session: AsyncSession, row: dict[str, Any]
) -> None:
    with pytest.raises(IntegrityError):
        await session.execute(insert(cpi_months).values(**row, fetched_at=FETCHED_AT))
