"""Repositorio de lotes de importación contra PostgreSQL real (ADR-0023).

Cada test se deshace al terminar. Además de leer y escribir, prueba que la base
repite las reglas del dominio.
"""

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from rinde.accounts.infrastructure.tables import accounts
from rinde.auth.infrastructure.tables import users
from rinde.imports.domain.batch import BatchLine, ImportBatch, LineStatus
from rinde.imports.domain.statement import LineError, LineProblem
from rinde.imports.infrastructure.repositories import SqlAlchemyBatchRepository
from rinde.imports.infrastructure.tables import import_batches, import_lines
from rinde.shared.domain.money import Currency

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


async def _owner_with_account(session: AsyncSession) -> tuple[UUID, UUID]:
    owner_id, account_id = uuid4(), uuid4()
    await session.execute(
        insert(users).values(
            id=owner_id,
            username=f"u{owner_id.hex[:12]}",
            password_hash="x",
            recovery_code_hash="x",
            created_at=NOW,
        )
    )
    await session.execute(
        insert(accounts).values(
            id=account_id,
            owner_id=owner_id,
            name="Macro",
            kind="bank",
            currency="ARS",
            created_at=NOW,
        )
    )
    return owner_id, account_id


def _batch(owner_id: UUID, account_id: UUID, created_at: datetime = NOW) -> ImportBatch:
    return ImportBatch(
        id=uuid4(),
        owner_id=owner_id,
        account_id=account_id,
        currency=Currency.ARS,
        file_name="octubre.csv",
        file_sha256="f" * 64,
        created_at=created_at,
        lines=[
            BatchLine(2, date(2026, 11, 3), "COTO", Decimal("-1500.50"), "a" * 64, LineStatus.NEW),
            BatchLine(
                3, date(2026, 11, 5), None, Decimal("250000.00"), "b" * 64, LineStatus.DUPLICATE
            ),
        ],
        errors=[LineError(4, LineProblem.DATE_INVALID)],
    )


async def test_a_batch_comes_back_the_same(session: AsyncSession) -> None:
    owner_id, account_id = await _owner_with_account(session)
    repository = SqlAlchemyBatchRepository(session)
    batch = _batch(owner_id, account_id)

    await repository.add(batch)

    assert await repository.get(batch.id, owner_id) == batch
    assert await repository.get(batch.id, uuid4()) is None


async def test_confirming_keeps_the_counts(session: AsyncSession) -> None:
    owner_id, account_id = await _owner_with_account(session)
    repository = SqlAlchemyBatchRepository(session)
    batch = _batch(owner_id, account_id)
    await repository.add(batch)
    confirmed = replace(batch, confirmed_at=NOW + timedelta(minutes=1), imported=1, skipped=0)

    await repository.save_confirmation(confirmed)

    assert await repository.get(batch.id, owner_id) == confirmed


async def test_only_a_pending_batch_of_the_owner_can_be_deleted(session: AsyncSession) -> None:
    owner_id, account_id = await _owner_with_account(session)
    repository = SqlAlchemyBatchRepository(session)
    pending = _batch(owner_id, account_id)
    confirmed = _batch(owner_id, account_id)
    await repository.add(pending)
    await repository.add(confirmed)
    await repository.save_confirmation(replace(confirmed, confirmed_at=NOW, imported=1))

    assert not await repository.delete(pending.id, uuid4())
    assert not await repository.delete(confirmed.id, owner_id)
    assert await repository.delete(pending.id, owner_id)
    assert await repository.get(pending.id, owner_id) is None


async def test_cleaning_removes_only_the_expired_pending(session: AsyncSession) -> None:
    owner_id, account_id = await _owner_with_account(session)
    repository = SqlAlchemyBatchRepository(session)
    old = _batch(owner_id, account_id, NOW - timedelta(hours=25))
    old_confirmed = _batch(owner_id, account_id, NOW - timedelta(days=30))
    fresh = _batch(owner_id, account_id, NOW - timedelta(hours=1))
    for batch in (old, old_confirmed, fresh):
        await repository.add(batch)
    await repository.save_confirmation(
        replace(old_confirmed, confirmed_at=NOW - timedelta(days=30))
    )

    await repository.delete_expired(NOW)

    assert await repository.get(old.id, owner_id) is None
    assert await repository.get(old_confirmed.id, owner_id) is not None
    assert await repository.get(fresh.id, owner_id) is not None


async def test_the_account_has_to_be_of_the_same_owner(session: AsyncSession) -> None:
    owner_id, _ = await _owner_with_account(session)
    _, theirs = await _owner_with_account(session)

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await SqlAlchemyBatchRepository(session).add(_batch(owner_id, theirs))


@pytest.mark.parametrize(
    "values",
    [
        {"file_sha256": "no"},
        {"file_name": "   "},
        {"imported": 1},
        {"imported": -1, "confirmed_at": NOW},
        {"confirmed_at": NOW - timedelta(days=1)},
    ],
)
async def test_the_database_repeats_the_rules_of_a_batch(
    session: AsyncSession, values: dict[str, Any]
) -> None:
    owner_id, account_id = await _owner_with_account(session)
    row = {
        "id": uuid4(),
        "owner_id": owner_id,
        "account_id": account_id,
        "currency": "ARS",
        "file_name": "octubre.csv",
        "file_sha256": "f" * 64,
        "created_at": NOW,
        "confirmed_at": None,
        "imported": 0,
        "skipped": 0,
        "errors": [],
    } | values

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(insert(import_batches).values(**row))


@pytest.mark.parametrize(
    "values",
    [{"amount": Decimal(0)}, {"number": 0}, {"fingerprint": "x"}, {"status": "maybe"}],
)
async def test_the_database_repeats_the_rules_of_a_line(
    session: AsyncSession, values: dict[str, Any]
) -> None:
    owner_id, account_id = await _owner_with_account(session)
    batch = replace(_batch(owner_id, account_id), lines=[])
    await SqlAlchemyBatchRepository(session).add(batch)
    row = {
        "batch_id": batch.id,
        "number": 2,
        "occurred_on": date(2026, 11, 3),
        "description": None,
        "amount": Decimal("-1.00"),
        "fingerprint": "a" * 64,
        "status": "new",
    } | values

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(insert(import_lines).values(**row))
