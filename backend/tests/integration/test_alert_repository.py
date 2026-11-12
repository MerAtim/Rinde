"""Repositorio de alertas contra PostgreSQL real. Cada test se deshace al terminar.

Además de leer y escribir, prueba que la base repite las reglas del dominio,
sobre todo la de "una vez por categoría, mes y umbral" (ADR-0022).
"""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from rinde.alerts.domain.alert import BudgetAlert, Threshold
from rinde.alerts.infrastructure.repositories import SqlAlchemyAlertRepository
from rinde.alerts.infrastructure.tables import budget_alerts
from rinde.auth.infrastructure.tables import users
from rinde.shared.domain.money import Currency, Money
from rinde.transactions.infrastructure.tables import categories

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)
OCTOBER = date(2026, 10, 1)
NOVEMBER = date(2026, 11, 1)


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


async def _category(session: AsyncSession, owner_id: UUID, kind: str = "expense") -> UUID:
    category_id = uuid4()
    await session.execute(
        insert(categories).values(
            id=category_id,
            owner_id=owner_id,
            name=f"Categoría {category_id.hex[:8]}",
            kind=kind,
            created_at=NOW,
        )
    )
    return category_id


def _alert(
    owner_id: UUID,
    category_id: UUID,
    threshold: Threshold = Threshold.WARNING,
    month: date = NOVEMBER,
    at: datetime = NOW,
) -> BudgetAlert:
    return BudgetAlert(
        id=uuid4(),
        owner_id=owner_id,
        category_id=category_id,
        month=month,
        threshold=threshold,
        limit=Money(Decimal("1000.00"), Currency.USD),
        spent=Money(Decimal("850.25"), Currency.USD),
        raised_at=at,
    )


async def test_adds_alerts_and_reads_them_newest_first(session: AsyncSession) -> None:
    repository = SqlAlchemyAlertRepository(session)
    owner = await _user(session)
    food = await _category(session, owner)
    older = _alert(owner, food, month=OCTOBER, at=NOW - timedelta(days=30))
    newer = _alert(owner, food, Threshold.OVER, at=NOW)

    assert await repository.add(older)
    assert await repository.add(newer)

    assert await repository.latest(owner, 10) == [newer, older]
    assert await repository.latest(owner, 1) == [newer]
    assert await repository.raised_in(owner, NOVEMBER) == {food: {Threshold.OVER}}


async def test_the_same_threshold_twice_in_a_month_is_not_added(session: AsyncSession) -> None:
    repository = SqlAlchemyAlertRepository(session)
    owner = await _user(session)
    food = await _category(session, owner)
    await repository.add(_alert(owner, food))

    # Otro pedido que evaluó a la vez: no es un error, y la sesión sigue usable.
    assert not await repository.add(_alert(owner, food, at=NOW + timedelta(seconds=1)))
    assert len(await repository.latest(owner, 10)) == 1
    assert await repository.add(_alert(owner, food, Threshold.OVER))


async def test_reading_marks_only_the_unread_alerts_of_the_owner(session: AsyncSession) -> None:
    repository = SqlAlchemyAlertRepository(session)
    owner, stranger = await _user(session), await _user(session)
    food = await _category(session, owner)
    theirs = await _category(session, stranger)
    mine = _alert(owner, food)
    other = _alert(stranger, theirs)
    await repository.add(mine)
    await repository.add(other)

    await repository.mark_read(owner, [mine.id, other.id], NOW + timedelta(hours=1))
    await repository.mark_read(owner, [mine.id], NOW + timedelta(hours=2))

    [read] = await repository.latest(owner, 10)
    assert read.read_at == NOW + timedelta(hours=1)
    assert await repository.unread_count(owner) == 0
    assert await repository.unread_count(stranger) == 1
    assert await repository.latest(stranger, 10) == [other]


async def test_deleting_a_category_takes_its_alerts_with_it(session: AsyncSession) -> None:
    repository = SqlAlchemyAlertRepository(session)
    owner = await _user(session)
    food = await _category(session, owner)
    await repository.add(_alert(owner, food))

    await session.execute(delete(categories).where(categories.c.id == food))

    assert await repository.latest(owner, 10) == []


@pytest.mark.parametrize(
    "values",
    [
        {"kind": "income"},
        {"month": date(2026, 11, 2)},
        {"threshold": "half"},
        {"limit_amount": Decimal("0")},
        {"spent_amount": Decimal("0")},
        {"currency": "BTC"},
        {"read_at": NOW - timedelta(seconds=1)},
    ],
)
async def test_the_database_repeats_the_rules_of_the_domain(
    session: AsyncSession, values: dict[str, Any]
) -> None:
    owner = await _user(session)
    food = await _category(session, owner)
    row = {
        "id": uuid4(),
        "owner_id": owner,
        "category_id": food,
        "month": NOVEMBER,
        "threshold": "warning",
        "limit_amount": Decimal("1000.00"),
        "spent_amount": Decimal("850.00"),
        "currency": "ARS",
        "raised_at": NOW,
    } | values

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(insert(budget_alerts).values(**row))


async def test_an_alert_needs_an_expense_category_of_the_same_owner(
    session: AsyncSession,
) -> None:
    repository = SqlAlchemyAlertRepository(session)
    owner, stranger = await _user(session), await _user(session)
    theirs = await _category(session, stranger)
    salary = await _category(session, owner, "income")

    for category in (theirs, salary):
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await repository.add(_alert(owner, category))
