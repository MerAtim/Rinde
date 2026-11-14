"""Las compras en cuotas, con todos los puertos en memoria (ADR-0026).

El reloj del arnés marca el 18 de septiembre de 2026, a las 9 de Buenos Aires.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from rinde.shared.domain.money import Currency, Money
from rinde.transactions.application.installments import PlanInput
from rinde.transactions.application.use_cases import TransactionInput
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.errors import (
    CategoryInUseError,
    IdempotencyKeyReusedError,
    InstallmentPlanNotFoundError,
    TransactionAccountArchivedError,
    TransactionAccountNotFoundError,
)
from rinde.transactions.domain.transaction import AuditAction
from tests.unit.transactions.fakes import Harness

pytestmark = pytest.mark.anyio

OWNER = uuid4()
STRANGER = uuid4()


def ars(amount: str) -> Money:
    return Money(Decimal(amount), Currency.ARS)


class Setup(Harness):
    def __init__(self) -> None:
        super().__init__()
        self.account_id = uuid4()
        self.accounts.add(self.account_id, OWNER)
        self.appliances = Category(
            uuid4(), OWNER, CategoryName.parse("Electro"), TransactionKind.EXPENSE, self.clock.now()
        )
        self.categories.rows[self.appliances.id] = self.appliances

    def purchase(
        self, first_on: date = date(2026, 9, 18), total: str = "120000.00", count: int = 6
    ) -> PlanInput:
        return PlanInput(
            account_id=self.account_id,
            category_id=self.appliances.id,
            total=Decimal(total),
            count=count,
            first_on=first_on,
            description="Heladera",
        )

    def generated_rows(self) -> list[tuple[int, date, Money]]:
        rows = [row for row in self.transactions.rows.values() if row.installment is not None]
        return sorted(
            (row.installment.number, row.occurred_on, row.money)
            for row in rows
            if row.installment is not None
        )


@pytest.fixture
def setup() -> Setup:
    return Setup()


async def test_a_purchase_today_brings_its_first_installment(setup: Setup) -> None:
    view = await setup.unit.create_plan.execute(OWNER, setup.purchase())

    assert setup.generated_rows() == [(1, date(2026, 9, 18), ars("20000.00"))]
    assert setup.audit.actions == [AuditAction.REGISTERED]
    assert setup.db.commits == 1
    assert view.pending == ars("100000.00")
    assert [item.generated is not None for item in view.installments] == [True] + [False] * 5
    created = next(iter(setup.transactions.rows.values()))
    assert created.description is not None
    assert created.description.value == "Heladera"
    assert created.installment is not None
    assert (created.installment.number, created.installment.count) == (1, 6)


async def test_an_old_purchase_brings_every_installment_already_due(setup: Setup) -> None:
    await setup.unit.create_plan.execute(OWNER, setup.purchase(first_on=date(2026, 6, 30)))

    assert [(number, day) for number, day, _ in setup.generated_rows()] == [
        (1, date(2026, 6, 30)),
        (2, date(2026, 7, 30)),
        (3, date(2026, 8, 30)),
    ]
    # Un evento por mes con gastos nuevos, después de confirmar.
    assert [event.occurred_on for event in setup.events.events] == [
        date(2026, 6, 30),
        date(2026, 7, 30),
        date(2026, 8, 30),
    ]
    assert setup.events.commits_at_publish == [1, 1, 1]


async def test_the_due_ones_are_generated_when_their_day_comes_and_only_once(setup: Setup) -> None:
    await setup.unit.create_plan.execute(OWNER, setup.purchase())

    assert await setup.unit.generate_due.execute(OWNER) == []
    setup.clock.advance(days=30)
    created = await setup.unit.generate_due.execute(OWNER)
    again = await setup.unit.generate_due.execute(OWNER)

    assert [row.installment.number for row in created if row.installment] == [2]
    assert again == []
    assert len(setup.generated_rows()) == 2


async def test_a_deleted_installment_is_not_generated_again(setup: Setup) -> None:
    await setup.unit.create_plan.execute(OWNER, setup.purchase())
    first = next(iter(setup.transactions.rows.values()))

    await setup.unit.delete.execute(OWNER, first.id)
    await setup.unit.generate_due.execute(OWNER)
    [view] = await setup.unit.list_plans.execute(OWNER)

    assert len(setup.generated_rows()) == 1
    assert view.installments[0].generated is not None
    assert view.installments[0].generated.is_deleted


async def test_a_cancelled_plan_keeps_what_was_paid_and_generates_nothing_else(
    setup: Setup,
) -> None:
    view = await setup.unit.create_plan.execute(OWNER, setup.purchase())

    cancelled = await setup.unit.cancel_plan.execute(OWNER, view.plan.id)
    again = await setup.unit.cancel_plan.execute(OWNER, view.plan.id)
    setup.clock.advance(days=90)
    await setup.unit.generate_due.execute(OWNER)

    assert cancelled.plan.is_cancelled
    assert again.plan.cancelled_at == cancelled.plan.cancelled_at
    assert cancelled.pending == ars("0.00")
    assert len(setup.generated_rows()) == 1


async def test_an_archived_account_still_receives_the_installments_owed(setup: Setup) -> None:
    await setup.unit.create_plan.execute(OWNER, setup.purchase())
    setup.accounts.add(setup.account_id, OWNER, archived=True)
    setup.clock.advance(days=30)

    await setup.unit.generate_due.execute(OWNER)

    assert len(setup.generated_rows()) == 2


async def test_a_new_plan_needs_an_active_account_of_its_owner(setup: Setup) -> None:
    with pytest.raises(TransactionAccountNotFoundError):
        await setup.unit.create_plan.execute(STRANGER, setup.purchase())
    setup.accounts.add(setup.account_id, OWNER, archived=True)
    with pytest.raises(TransactionAccountArchivedError):
        await setup.unit.create_plan.execute(OWNER, setup.purchase())
    assert setup.installments.rows == {}


async def test_the_same_key_does_not_create_two_plans(setup: Setup) -> None:
    first = await setup.unit.create_plan.execute(OWNER, setup.purchase(), "clave-1")
    again = await setup.unit.create_plan.execute(OWNER, setup.purchase(), "clave-1")

    assert again.plan.id == first.plan.id
    assert len(setup.installments.rows) == 1
    assert len(setup.generated_rows()) == 1
    with pytest.raises(IdempotencyKeyReusedError):
        await setup.unit.create_plan.execute(OWNER, setup.purchase(count=3), "clave-1")


async def test_someone_elses_plan_does_not_exist(setup: Setup) -> None:
    view = await setup.unit.create_plan.execute(OWNER, setup.purchase())

    with pytest.raises(InstallmentPlanNotFoundError):
        await setup.unit.cancel_plan.execute(STRANGER, view.plan.id)
    assert await setup.unit.list_plans.execute(STRANGER) == []
    assert await setup.unit.generate_due.execute(STRANGER) == []


async def test_a_category_with_a_plan_cannot_be_deleted(setup: Setup) -> None:
    view = await setup.unit.create_plan.execute(OWNER, setup.purchase())
    first = next(iter(setup.transactions.rows.values()))
    await setup.unit.delete.execute(OWNER, first.id)
    await setup.unit.cancel_plan.execute(OWNER, view.plan.id)

    with pytest.raises(CategoryInUseError):
        await setup.unit.delete_category.execute(OWNER, setup.appliances.id)


async def test_editing_an_installment_keeps_it_as_that_installment(setup: Setup) -> None:
    await setup.unit.create_plan.execute(OWNER, setup.purchase())
    first = next(iter(setup.transactions.rows.values()))

    edited = await setup.unit.edit.execute(
        OWNER,
        first.id,
        TransactionInput(
            account_id=setup.account_id,
            kind=TransactionKind.EXPENSE,
            amount=Decimal("21000.00"),
            category_id=setup.appliances.id,
            occurred_on=first.occurred_on,
            description="Heladera con interés",
        ),
    )

    assert edited.installment == first.installment
