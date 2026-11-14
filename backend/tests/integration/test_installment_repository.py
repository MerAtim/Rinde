"""Planes de cuotas contra PostgreSQL real (ADR-0026). Cada test se deshace al terminar."""

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
from rinde.transactions.domain.category import Category
from rinde.transactions.domain.installments import InstallmentPlan, PlanDraft, plan
from rinde.transactions.domain.transaction import (
    InstallmentRef,
    TargetAccount,
    Transaction,
    register,
)
from rinde.transactions.infrastructure.repositories import (
    SqlAlchemyInstallmentPlanRepository,
    SqlAlchemyTransactionRepository,
)
from rinde.transactions.infrastructure.tables import installment_plans
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
        self.plans = SqlAlchemyInstallmentPlanRepository(session)
        self.transactions = SqlAlchemyTransactionRepository(session)

    async def plan(self, first_on: date = date(2026, 8, 18), count: int = 3) -> InstallmentPlan:
        created = plan(
            PlanDraft(Money(Decimal("100.00"), Currency.ARS), count, self.category, first_on),
            self.account,
            plan_id=uuid4(),
            owner_id=self.owner,
            at=NOW,
        )
        await self.plans.add(created)
        return created

    def installment(self, created: InstallmentPlan, number: int) -> Transaction:
        item = created.schedule()[number - 1]
        return register(
            created.draft(item, self.category),
            self.account,
            transaction_id=uuid4(),
            owner_id=self.owner,
            at=NOW,
            installment=InstallmentRef(created.id, number, created.count),
        )


@pytest.fixture
async def world(session: AsyncSession) -> World:
    owner = await _user(session, "mechi")
    return World(session, owner, await _account(session, owner), await _category(session, owner))


async def test_a_plan_comes_back_as_it_was_saved(world: World) -> None:
    created = await world.plan()

    assert await world.plans.get(created.id, world.owner) == created
    assert await world.plans.get(created.id, uuid4()) is None
    assert await world.plans.list_for_owner(world.owner) == [created]
    assert await world.plans.count_by_category(world.category.id, world.owner) == 1


async def test_cancelling_is_the_only_thing_that_changes(world: World) -> None:
    created = await world.plan()

    await world.plans.save(created.cancelled(NOW))

    stored = await world.plans.get(created.id, world.owner)
    assert stored is not None
    assert stored.cancelled_at == NOW


async def test_an_installment_is_generated_once_and_reads_back_with_its_plan(
    world: World,
) -> None:
    created = await world.plan()
    first = world.installment(created, 1)

    assert await world.transactions.add_installment(first)
    assert not await world.transactions.add_installment(world.installment(created, 1))

    stored = await world.transactions.get(first.id, world.owner)
    assert stored is not None
    assert stored.installment == InstallmentRef(created.id, 1, 3)


async def test_a_deleted_installment_still_counts_as_generated(world: World) -> None:
    created = await world.plan()
    first = world.installment(created, 1)
    await world.transactions.add_installment(first)
    await world.transactions.save(first.deleted(NOW))

    generated = await world.plans.generated(world.owner, [created.id])

    assert generated[created.id][1].transaction_id == first.id
    assert generated[created.id][1].is_deleted
    assert await world.plans.generated(uuid4(), [created.id]) == {}
    assert await world.plans.generated(world.owner, []) == {}


async def test_the_database_ties_each_installment_to_its_plan(world: World) -> None:
    created = await world.plan()
    other_account = await _account(world.session, world.owner)

    # Una cuota que dice ser de otra cuenta que la de su plan no entra.
    stray = replace(world.installment(created, 1), account_id=other_account.id)
    with pytest.raises(IntegrityError):
        async with world.session.begin_nested():
            await world.transactions.add_installment(stray)

    # Ni un número que pasa de la cantidad.
    beyond = replace(world.installment(created, 1), installment=InstallmentRef(created.id, 4, 3))
    with pytest.raises(IntegrityError):
        async with world.session.begin_nested():
            await world.transactions.add_installment(beyond)


async def test_the_database_rejects_a_plan_the_domain_rejects(world: World) -> None:
    created = await world.plan()

    with pytest.raises(IntegrityError):
        async with world.session.begin_nested():
            await world.session.execute(
                update(installment_plans)
                .where(installment_plans.c.id == created.id)
                .values(count=1)
            )
