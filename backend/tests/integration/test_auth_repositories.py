"""Repositorios de autenticación contra PostgreSQL real. Cada test se deshace al terminar."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from rinde.auth.application.ports import Session
from rinde.auth.domain.errors import UsernameTakenError
from rinde.auth.domain.user import User
from rinde.auth.domain.username import Username
from rinde.auth.infrastructure.repositories import (
    SqlAlchemyFailedAttemptRepository,
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

NOW = datetime(2026, 9, 11, 12, tzinfo=UTC)


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


def _user(name: str = "mechi") -> User:
    return User(
        id=uuid4(),
        username=Username.parse(name),
        password_hash="hash-de-contraseña",
        recovery_code_hash="hash-de-código",
        created_at=NOW,
    )


async def test_users_are_found_by_username_and_by_id(session: AsyncSession) -> None:
    users = SqlAlchemyUserRepository(session)
    user = _user()

    await users.add(user)

    assert await users.by_username(user.username) == user
    assert await users.by_id(user.id) == user
    assert await users.by_username(Username.parse("nadie")) is None


async def test_the_database_rejects_duplicate_usernames(session: AsyncSession) -> None:
    users = SqlAlchemyUserRepository(session)
    await users.add(_user())

    with pytest.raises(UsernameTakenError):
        await users.add(_user())


async def test_credentials_can_be_replaced(session: AsyncSession) -> None:
    users = SqlAlchemyUserRepository(session)
    user = _user()
    await users.add(user)

    await users.update_credentials(user.id, password_hash="nuevo", recovery_code_hash="otro")

    stored = await users.by_id(user.id)
    assert stored is not None
    assert (stored.password_hash, stored.recovery_code_hash) == ("nuevo", "otro")


async def test_sessions_can_be_found_and_revoked(session: AsyncSession) -> None:
    users = SqlAlchemyUserRepository(session)
    sessions = SqlAlchemySessionRepository(session)
    user = _user()
    await users.add(user)
    first, second = (
        Session(
            token_hash=f"{n:064d}",
            user_id=user.id,
            created_at=NOW,
            expires_at=NOW + timedelta(days=30),
        )
        for n in (1, 2)
    )
    await sessions.add(first)
    await sessions.add(second)

    assert await sessions.by_token_hash(first.token_hash) == first
    await sessions.delete(first.token_hash)
    assert await sessions.by_token_hash(first.token_hash) is None
    await sessions.delete_all_for_user(user.id)
    assert await sessions.by_token_hash(second.token_hash) is None


async def test_failed_attempts_are_counted_inside_the_window(session: AsyncSession) -> None:
    attempts = SqlAlchemyFailedAttemptRepository(session)
    username = Username.parse("mechi")
    await attempts.record(username, NOW - timedelta(minutes=30))
    await attempts.record(username, NOW - timedelta(minutes=5))
    await attempts.record(Username.parse("otra"), NOW)

    assert await attempts.count_since(username, NOW - timedelta(minutes=15)) == 1
    await attempts.clear(username)
    assert await attempts.count_since(username, NOW - timedelta(days=1)) == 0
