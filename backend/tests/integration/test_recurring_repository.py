"""Reglas recurrentes contra PostgreSQL real (ADR-0027). Cada test se deshace al terminar."""

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from rinde.shared.domain.money import Currency, Money
from rinde.transactions.domain.category import Category, TransactionKind
from rinde.transactions.domain.recurring import Frequency, RecurringRule, RuleDraft, recurring_rule
from rinde.transactions.domain.transaction import (
    Description,
    InstallmentRef,
    RecurrenceRef,
    TargetAccount,
    Transaction,
    register,
)
from rinde.transactions.infrastructure.repositories import (
    SqlAlchemyRecurringRuleRepository,
    SqlAlchemyTransactionRepository,
)
from rinde.transactions.infrastructure.tables import recurring_rules
from tests.integration.test_transaction_repository import _account, _category, _user

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


class World:
    def __init__(
        self, session: AsyncSession, owner: UUID, account: TargetAccount, category: Category
    ) -> None:
        self.session = session
        self.owner = owner
        self.account = account
        self.category = category
        self.rules = SqlAlchemyRecurringRuleRepository(session)
        self.transactions = SqlAlchemyTransactionRepository(session)

    async def rule(self, starts_on: date = date(2026, 8, 18)) -> RecurringRule:
        created = recurring_rule(
            RuleDraft(
                TransactionKind.EXPENSE,
                Money(Decimal("450000.00"), Currency.ARS),
                self.category,
                Frequency.MONTHLY,
                starts_on,
                Description.parse("Alquiler"),
            ),
            self.account,
            rule_id=uuid4(),
            owner_id=self.owner,
            at=NOW,
        )
        await self.rules.add(created)
        return created

    def occurrence(self, rule: RecurringRule, number: int) -> Transaction:
        return register(
            rule.draft(rule.occurrence(number), self.category),
            self.account,
            transaction_id=uuid4(),
            owner_id=self.owner,
            at=NOW,
            recurrence=RecurrenceRef(rule.id, number),
        )


@pytest.fixture
async def world(session: AsyncSession) -> World:
    owner = await _user(session, "mechi")
    return World(session, owner, await _account(session, owner), await _category(session, owner))


async def test_a_rule_comes_back_as_it_was_saved(world: World) -> None:
    created = await world.rule()

    assert await world.rules.get(created.id, world.owner) == created
    assert await world.rules.get(created.id, uuid4()) is None
    assert await world.rules.list_for_owner(world.owner) == [created]
    assert await world.rules.count_by_category(world.category.id, world.owner) == 1


async def test_the_active_ones_come_first(world: World) -> None:
    older = await world.rule(date(2026, 6, 1))
    newer = await world.rule(date(2026, 9, 1))
    await world.rules.save(newer.cancelled(NOW))

    listed = await world.rules.list_for_owner(world.owner)

    assert [item.id for item in listed] == [older.id, newer.id]


async def test_the_amount_the_description_and_cancelling_are_saved(world: World) -> None:
    created = await world.rule()
    changed = created.changed(Money(Decimal("520000.00"), Currency.ARS), None).cancelled(NOW)

    await world.rules.save(changed)

    assert await world.rules.get(created.id, world.owner) == changed


async def test_a_time_is_generated_once_and_reads_back_with_its_rule(world: World) -> None:
    created = await world.rule()
    first = world.occurrence(created, 1)

    assert await world.transactions.add_occurrence(first)
    assert not await world.transactions.add_occurrence(world.occurrence(created, 1))

    stored = await world.transactions.get(first.id, world.owner)
    assert stored is not None
    assert stored.recurrence == RecurrenceRef(created.id, 1)


async def test_the_last_one_generated_is_the_highest_number_of_each_rule(world: World) -> None:
    created = await world.rule()
    other = await world.rule()
    for number in (1, 2):
        await world.transactions.add_occurrence(world.occurrence(created, number))

    last = await world.rules.last_generated(world.owner, [created.id, other.id])

    assert last == {created.id: 2}
    assert await world.rules.last_generated(uuid4(), [created.id]) == {}
    assert await world.rules.last_generated(world.owner, []) == {}


async def test_a_deleted_time_still_counts_as_generated(world: World) -> None:
    created = await world.rule()
    first = world.occurrence(created, 1)
    await world.transactions.add_occurrence(first)
    await world.transactions.save(first.deleted(NOW))

    assert await world.rules.last_generated(world.owner, [created.id]) == {created.id: 1}


async def test_the_database_ties_each_time_to_its_rule(world: World) -> None:
    created = await world.rule()
    other_account = await _account(world.session, world.owner)

    # Una vez que dice ser de otra cuenta que la de su regla no entra.
    stray = replace(world.occurrence(created, 1), account_id=other_account.id)
    with pytest.raises(IntegrityError, match="occurrence_of_the_same_rule_owner_and_account"):
        async with world.session.begin_nested():
            await world.transactions.add_occurrence(stray)

    # Ni un movimiento que dice ser cuota y recurrente a la vez.
    both = replace(world.occurrence(created, 1), installment=InstallmentRef(uuid4(), 1, 3))
    with pytest.raises(IntegrityError, match="one_origin_at_most"):
        async with world.session.begin_nested():
            await world.transactions.add_occurrence(both)


async def test_the_database_rejects_a_rule_the_domain_rejects(world: World) -> None:
    created = await world.rule()

    with pytest.raises(IntegrityError, match="frequency_known"):
        async with world.session.begin_nested():
            await world.session.execute(
                update(recurring_rules)
                .where(recurring_rules.c.id == created.id)
                .values(frequency="daily")
            )
