"""Repositorio de presupuestos contra PostgreSQL real. Cada test se deshace al terminar.

Además de leer y escribir, prueba que la base repite las reglas del dominio: si
alguien escribiera una fila sin pasar por él, la rechazaría igual (ADR-0021).
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

from rinde.auth.infrastructure.tables import users
from rinde.budgets.domain.budget import BudgetLimit
from rinde.budgets.domain.errors import BudgetCategoryNotFoundError
from rinde.budgets.infrastructure.repositories import SqlAlchemyBudgetRepository
from rinde.budgets.infrastructure.tables import budget_limits
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


def _limit(
    owner_id: UUID,
    category_id: UUID,
    since: date,
    amount: str | None,
    at: datetime = NOW,
    currency: Currency = Currency.ARS,
) -> BudgetLimit:
    return BudgetLimit(
        id=uuid4(),
        owner_id=owner_id,
        category_id=category_id,
        since=since,
        limit=None if amount is None else Money(Decimal(amount), currency),
        recorded_at=at,
    )


async def test_adds_vigencies_and_reads_them_back_in_order(session: AsyncSession) -> None:
    repository = SqlAlchemyBudgetRepository(session)
    owner = await _user(session)
    food = await _category(session, owner)
    rows = [
        _limit(owner, food, NOVEMBER, None, NOW + timedelta(hours=1)),
        _limit(owner, food, OCTOBER, "300000.00"),
        _limit(owner, food, NOVEMBER, "500.00", NOW, Currency.USD),
    ]
    for row in rows:
        await repository.add(row)

    history = await repository.history(owner, NOVEMBER)

    assert history == [rows[1], rows[2], rows[0]]


async def test_history_stops_at_the_month_and_at_the_owner(session: AsyncSession) -> None:
    repository = SqlAlchemyBudgetRepository(session)
    owner, stranger = await _user(session), await _user(session)
    food = await _category(session, owner)
    theirs = await _category(session, stranger)
    await repository.add(_limit(owner, food, OCTOBER, "1000.00"))
    await repository.add(_limit(owner, food, NOVEMBER, "2000.00"))
    await repository.add(_limit(stranger, theirs, OCTOBER, "3000.00"))

    history = await repository.history(owner, OCTOBER)

    assert [row.limit for row in history] == [Money(Decimal("1000.00"), Currency.ARS)]


async def test_a_category_of_someone_else_is_rejected_as_not_found(
    session: AsyncSession,
) -> None:
    repository = SqlAlchemyBudgetRepository(session)
    owner, stranger = await _user(session), await _user(session)
    theirs = await _category(session, stranger)

    with pytest.raises(BudgetCategoryNotFoundError):
        await repository.add(_limit(owner, theirs, NOVEMBER, "1000.00"))
    # El punto de guardado deja la sesión usable después del rechazo.
    assert await repository.history(owner, NOVEMBER) == []


async def test_an_income_category_cannot_have_a_limit(session: AsyncSession) -> None:
    owner = await _user(session)
    salary = await _category(session, owner, "income")

    with pytest.raises(BudgetCategoryNotFoundError):
        await SqlAlchemyBudgetRepository(session).add(_limit(owner, salary, NOVEMBER, "1.00"))


async def test_deleting_a_category_takes_its_limits_with_it(session: AsyncSession) -> None:
    repository = SqlAlchemyBudgetRepository(session)
    owner = await _user(session)
    food = await _category(session, owner)
    await repository.add(_limit(owner, food, OCTOBER, "1000.00"))

    await session.execute(delete(categories).where(categories.c.id == food))

    assert await repository.history(owner, NOVEMBER) == []


async def test_two_vigencies_of_a_category_cannot_tie(session: AsyncSession) -> None:
    repository = SqlAlchemyBudgetRepository(session)
    owner = await _user(session)
    food = await _category(session, owner)
    await repository.add(_limit(owner, food, NOVEMBER, "1000.00"))

    with pytest.raises(IntegrityError):
        await repository.add(_limit(owner, food, NOVEMBER, "2000.00"))


@pytest.mark.parametrize(
    "values",
    [
        {"amount": Decimal("0"), "currency": "ARS"},
        {"amount": Decimal("10.00"), "currency": "BTC"},
        {"amount": Decimal("10.00"), "currency": None},
        {"amount": None, "currency": "ARS"},
        {"since": date(2026, 11, 2)},
        {"kind": "income"},
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
        "since": NOVEMBER,
        "amount": Decimal("1000.00"),
        "currency": "ARS",
        "recorded_at": NOW,
    } | values

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(insert(budget_limits).values(**row))
