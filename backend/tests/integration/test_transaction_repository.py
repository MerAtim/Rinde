"""Repositorios de movimientos contra PostgreSQL real. Cada test se deshace al terminar."""

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from rinde.accounts.infrastructure.tables import accounts
from rinde.auth.infrastructure.tables import users
from rinde.shared.domain.money import Currency, Money
from rinde.transactions.application.ports import TransactionFilters
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.transaction import (
    AuditAction,
    Description,
    Draft,
    TargetAccount,
    Transaction,
    register,
)
from rinde.transactions.infrastructure.repositories import (
    SqlAlchemyAuditLog,
    SqlAlchemyCategoryRepository,
    SqlAlchemyIdempotencyStore,
    SqlAlchemyTransactionRepository,
)
from rinde.transactions.infrastructure.tables import transaction_audit, transactions

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)


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


async def _account(
    session: AsyncSession, owner_id: UUID, currency: Currency = Currency.ARS
) -> TargetAccount:
    account_id = uuid4()
    await session.execute(
        insert(accounts).values(
            id=account_id,
            owner_id=owner_id,
            name="Galicia sueldo",
            kind="bank",
            currency=currency.value,
            created_at=NOW,
        )
    )
    return TargetAccount(id=account_id, currency=currency)


async def _category(
    session: AsyncSession,
    owner_id: UUID,
    kind: TransactionKind = TransactionKind.EXPENSE,
    name: str = "Supermercado",
) -> Category:
    category = Category(
        id=uuid4(),
        owner_id=owner_id,
        name=CategoryName.parse(name),
        kind=kind,
        created_at=NOW,
    )
    await SqlAlchemyCategoryRepository(session).add(category)
    return category


def _a_transaction(
    owner_id: UUID,
    account: TargetAccount,
    category: Category,
    amount: str = "1500.00",
    day: int = 18,
) -> Transaction:
    draft = Draft(
        kind=category.kind,
        money=Money(Decimal(amount), account.currency),
        category=category,
        occurred_on=date(2026, 9, day),
        description=Description.parse("Coto"),
    )
    return register(draft, account, transaction_id=uuid4(), owner_id=owner_id, at=NOW)


async def test_a_saved_movement_comes_back_the_same(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    category = await _category(session, owner_id)
    repository = SqlAlchemyTransactionRepository(session)
    movement = _a_transaction(owner_id, account, category, "15300.50")

    await repository.add(movement)

    assert await repository.get(movement.id, owner_id) == movement


async def test_no_reading_brings_back_a_deleted_movement(session: AsyncSession) -> None:
    """La red que sostiene el borrado lógico (ADR-0011): si una lectura nueva se
    olvida de filtrar, este test falla."""
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    category = await _category(session, owner_id)
    repository = SqlAlchemyTransactionRepository(session)
    movement = _a_transaction(owner_id, account, category, "1000.00")
    await repository.add(movement)

    await repository.save(movement.deleted(NOW))

    page = await repository.page_for_owner(owner_id, TransactionFilters(), cursor=None, limit=50)
    assert page.items == []
    assert await repository.balances_for_owner(owner_id) == []
    assert await repository.count_by_category(category.id, owner_id) == 0
    # Solo `get` lo sigue viendo, que es lo que permite deshacer.
    found = await repository.get(movement.id, owner_id)
    assert found is not None
    assert found.is_deleted


async def test_the_balance_is_the_sum_of_the_movements(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    expenses = await _category(session, owner_id)
    incomes = await _category(session, owner_id, TransactionKind.INCOME, "Sueldo")
    repository = SqlAlchemyTransactionRepository(session)

    await repository.add(_a_transaction(owner_id, account, incomes, "100000.00"))
    await repository.add(_a_transaction(owner_id, account, expenses, "15300.50"))

    balances = await repository.balances_for_owner(owner_id)

    assert len(balances) == 1
    assert balances[0].account_id == account.id
    assert balances[0].balance == Money(Decimal("84699.50"), Currency.ARS)


async def test_the_pages_do_not_repeat_or_skip_rows(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    category = await _category(session, owner_id)
    repository = SqlAlchemyTransactionRepository(session)
    # Dos el mismo día, para que el desempate por identificador tenga que trabajar.
    for day in (15, 16, 17, 17):
        await repository.add(_a_transaction(owner_id, account, category, day=day))

    first = await repository.page_for_owner(owner_id, TransactionFilters(), cursor=None, limit=2)
    second = await repository.page_for_owner(
        owner_id, TransactionFilters(), cursor=first.next_cursor, limit=2
    )

    seen = [row.id for row in first.items + second.items]
    assert len(set(seen)) == 4
    assert [row.occurred_on.day for row in first.items] == [17, 17]
    assert second.next_cursor is None


async def test_nobody_reads_the_movements_of_another_person(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    stranger_id = await _user(session, "otra")
    account = await _account(session, owner_id)
    category = await _category(session, owner_id)
    repository = SqlAlchemyTransactionRepository(session)
    movement = _a_transaction(owner_id, account, category)
    await repository.add(movement)

    assert await repository.get(movement.id, stranger_id) is None
    page = await repository.page_for_owner(stranger_id, TransactionFilters(), cursor=None, limit=50)
    assert page.items == []
    assert await repository.balances_for_owner(stranger_id) == []


async def test_the_database_rejects_a_movement_in_another_currency(session: AsyncSession) -> None:
    """La regla vive también en la base: la clave foránea ata la moneda a la cuenta."""
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id, Currency.ARS)
    category = await _category(session, owner_id)

    with pytest.raises(IntegrityError):
        await session.execute(
            insert(transactions).values(
                id=uuid4(),
                owner_id=owner_id,
                account_id=account.id,
                currency="USD",
                kind="expense",
                amount=Decimal("10.00"),
                category_id=category.id,
                occurred_on=date(2026, 9, 18),
                created_at=NOW,
                updated_at=NOW,
            )
        )


async def test_the_database_rejects_an_income_with_an_expense_category(
    session: AsyncSession,
) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    expenses = await _category(session, owner_id)

    with pytest.raises(IntegrityError):
        await session.execute(
            insert(transactions).values(
                id=uuid4(),
                owner_id=owner_id,
                account_id=account.id,
                currency="ARS",
                kind="income",
                amount=Decimal("10.00"),
                category_id=expenses.id,
                occurred_on=date(2026, 9, 18),
                created_at=NOW,
                updated_at=NOW,
            )
        )


@pytest.mark.parametrize(
    ("amount", "currency"),
    [(Decimal("-1.00"), "ARS"), (Decimal("0.00"), "ARS"), (Decimal("10.999"), "ARS")],
)
async def test_the_database_rejects_amounts_that_do_not_fit(
    session: AsyncSession, amount: Decimal, currency: str
) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id, Currency(currency))
    category = await _category(session, owner_id)

    with pytest.raises(IntegrityError):
        await session.execute(
            insert(transactions).values(
                id=uuid4(),
                owner_id=owner_id,
                account_id=account.id,
                currency=currency,
                kind="expense",
                amount=amount,
                category_id=category.id,
                occurred_on=date(2026, 9, 18),
                created_at=NOW,
                updated_at=NOW,
            )
        )


async def test_the_audit_log_only_accepts_inserts(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    category = await _category(session, owner_id)
    movement = _a_transaction(owner_id, account, category)
    await SqlAlchemyTransactionRepository(session).add(movement)
    await SqlAlchemyAuditLog(session).record(AuditAction.REGISTERED, movement, NOW)

    entry = (
        (
            await session.execute(
                select(transaction_audit).where(transaction_audit.c.transaction_id == movement.id)
            )
        )
        .mappings()
        .one()
    )
    assert entry["action"] == "registered"
    assert entry["snapshot"]["amount"] == "1500.00"

    # Cada intento va en su propio punto de retorno: al fallar se deshace solo él,
    # y la fila de auditoría sigue ahí para el intento siguiente.
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            await session.execute(
                update(transaction_audit)
                .where(transaction_audit.c.id == entry["id"])
                .values(action="edited")
            )
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            await session.execute(
                text("DELETE FROM transaction_audit WHERE id = :id"), {"id": entry["id"]}
            )

    still_there = await session.execute(
        select(transaction_audit).where(transaction_audit.c.id == entry["id"])
    )
    assert still_there.mappings().one()["action"] == "registered"


async def test_the_same_seeds_are_not_planted_twice(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    repository = SqlAlchemyCategoryRepository(session)
    seeds = [
        Category(
            id=uuid4(),
            owner_id=owner_id,
            name=CategoryName.parse("Supermercado"),
            kind=TransactionKind.EXPENSE,
            created_at=NOW,
            slug="supermercado",
        )
    ]

    await repository.add_seeds(seeds)
    # Otra siembra simultánea: el mismo identificador sembrado, otra fila.
    await repository.add_seeds([replace(seeds[0], id=uuid4())])

    assert len(await repository.list_for_owner(owner_id)) == 1


async def test_an_idempotency_key_remembers_its_movement(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    category = await _category(session, owner_id)
    movement = _a_transaction(owner_id, account, category)
    await SqlAlchemyTransactionRepository(session).add(movement)
    store = SqlAlchemyIdempotencyStore(session)

    await store.remember(owner_id, "clave-1", "huella", movement.id, NOW)

    assert await store.recall(owner_id, "clave-1") == ("huella", movement.id)
    assert await store.recall(owner_id, "otra") is None

    await store.forget_expired(NOW + timedelta(days=1))
    assert await store.recall(owner_id, "clave-1") is None
