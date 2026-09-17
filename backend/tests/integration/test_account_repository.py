"""Repositorio de cuentas contra PostgreSQL real. Cada test se deshace al terminar."""

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from rinde.accounts.domain.account import Account, AccountKind, AccountName
from rinde.accounts.infrastructure.repositories import SqlAlchemyAccountRepository
from rinde.auth.infrastructure.tables import users
from rinde.shared.domain.money import Currency

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


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


async def _user(session: AsyncSession, name: str) -> UUID:
    user_id = uuid4()
    await session.execute(
        insert(users).values(
            id=user_id,
            username=name,
            password_hash="x",
            recovery_code_hash="x",
            created_at=NOW,
        )
    )
    return user_id


def _account(owner_id: UUID, name: str = "Galicia", at: datetime = NOW) -> Account:
    return Account(
        id=uuid4(),
        owner_id=owner_id,
        name=AccountName.parse(name),
        kind=AccountKind.BANK,
        currency=Currency.ARS,
        created_at=at,
    )


async def test_an_account_is_only_found_by_its_owner(session: AsyncSession) -> None:
    repository = SqlAlchemyAccountRepository(session)
    owner, stranger = await _user(session, "duena"), await _user(session, "intrusa")
    account = _account(owner)
    await repository.add(account)

    assert await repository.get(account.id, owner) == account
    assert await repository.get(account.id, stranger) is None
    assert await repository.list_for_owner(stranger, include_archived=True) == []


async def test_the_list_is_ordered_and_hides_archived_accounts(session: AsyncSession) -> None:
    repository = SqlAlchemyAccountRepository(session)
    owner = await _user(session, "duena")
    second = _account(owner, "Segunda", NOW + timedelta(minutes=1))
    first = _account(owner, "Primera", NOW)
    archived = _account(owner, "Archivada", NOW + timedelta(minutes=2)).archived(
        NOW + timedelta(days=1)
    )
    for account in (second, first, archived):
        await repository.add(account)

    visible = await repository.list_for_owner(owner, include_archived=False)
    everything = await repository.list_for_owner(owner, include_archived=True)

    assert [a.name.value for a in visible] == ["Primera", "Segunda"]
    assert [a.name.value for a in everything] == ["Primera", "Segunda", "Archivada"]


async def test_saving_changes_only_the_name_and_the_archive_date(session: AsyncSession) -> None:
    repository = SqlAlchemyAccountRepository(session)
    owner = await _user(session, "duena")
    account = _account(owner)
    await repository.add(account)

    changed = account.renamed(AccountName.parse("Galicia ahorro")).archived(NOW)
    await repository.save(changed)

    assert await repository.get(account.id, owner) == changed


async def test_saving_with_another_owner_changes_nothing(session: AsyncSession) -> None:
    repository = SqlAlchemyAccountRepository(session)
    owner, stranger = await _user(session, "duena"), await _user(session, "intrusa")
    account = _account(owner)
    await repository.add(account)

    await repository.save(replace(account, owner_id=stranger, name=AccountName.parse("Robada")))

    assert await repository.get(account.id, owner) == account


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("currency", "'BTC'"),  # en una cuenta bancaria
        ("currency", "'EUR'"),
        ("kind", "'alcancia'"),
        ("name", "'   '"),
        ("archived_at", "'2020-01-01T00:00:00+00:00'"),  # antes de crearse
    ],
)
async def test_the_database_rejects_rows_that_break_the_rules(
    session: AsyncSession, column: str, value: str
) -> None:
    """Si algún día alguien escribe sin pasar por el dominio, la base lo frena igual."""
    repository = SqlAlchemyAccountRepository(session)
    owner = await _user(session, "duena")
    account = _account(owner)
    await repository.add(account)

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                text(f"UPDATE accounts SET {column} = {value} WHERE id = :id"),  # noqa: S608
                {"id": account.id},
            )


async def test_an_account_needs_an_existing_owner(session: AsyncSession) -> None:
    repository = SqlAlchemyAccountRepository(session)

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await repository.add(_account(uuid4()))
