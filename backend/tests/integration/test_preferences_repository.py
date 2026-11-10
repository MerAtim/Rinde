"""Repositorio de preferencias contra PostgreSQL real. Cada test se deshace al terminar."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from rinde.auth.infrastructure.tables import users
from rinde.preferences.domain.preferences import Preferences
from rinde.preferences.infrastructure.repositories import SqlAlchemyPreferencesRepository
from rinde.preferences.infrastructure.tables import user_preferences
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)


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


async def _user(session: AsyncSession) -> UUID:
    user_id = uuid4()
    await session.execute(
        insert(users).values(
            id=user_id,
            username=f"u{user_id.hex[:12]}",
            password_hash="x",
            recovery_code_hash="x",
            created_at=NOW,
        )
    )
    return user_id


async def test_nothing_is_stored_until_something_changes(session: AsyncSession) -> None:
    assert await SqlAlchemyPreferencesRepository(session).get(await _user(session)) is None


async def test_saving_twice_replaces_the_same_row(session: AsyncSession) -> None:
    repository = SqlAlchemyPreferencesRepository(session)
    owner = await _user(session)

    await repository.save(Preferences(owner, Currency.USD, RateType.BLUE, NOW))
    await repository.save(Preferences(owner, Currency.ARS, RateType.CCL, NOW))

    assert await repository.get(owner) == Preferences(owner, Currency.ARS, RateType.CCL, NOW)


async def test_deleting_the_user_deletes_the_preferences(session: AsyncSession) -> None:
    repository = SqlAlchemyPreferencesRepository(session)
    owner = await _user(session)
    await repository.save(Preferences(owner, Currency.USD, RateType.BLUE, NOW))

    await session.execute(delete(users).where(users.c.id == owner))

    assert await repository.get(owner) is None


@pytest.mark.parametrize(
    "fields",
    [{"reference_currency": "BTC"}, {"rate_type": "mayorista"}, {"owner_id": uuid4()}],
)
async def test_the_database_rejects_an_impossible_row(
    session: AsyncSession, fields: dict[str, Any]
) -> None:
    row = {
        "owner_id": await _user(session),
        "reference_currency": "ARS",
        "rate_type": "mep",
        "updated_at": NOW,
        **fields,
    }

    with pytest.raises(IntegrityError):
        await session.execute(insert(user_preferences).values(row))
