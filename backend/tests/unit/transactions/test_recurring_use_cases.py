"""Los movimientos recurrentes, con todos los puertos en memoria (ADR-0027).

El reloj del arnés marca el 18 de septiembre de 2026, a las 9 de Buenos Aires.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from rinde.shared.domain.money import AmountTooPreciseError, Currency, Money
from rinde.transactions.application.recurring import RuleChange, RuleInput
from rinde.transactions.application.use_cases import TransactionInput
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.errors import (
    CategoryInUseError,
    IdempotencyKeyReusedError,
    RecurringRuleCancelledError,
    RecurringRuleNotFoundError,
    TransactionAccountArchivedError,
    TransactionAccountNotFoundError,
)
from rinde.transactions.domain.recurring import Frequency
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
        self.rent = Category(
            uuid4(),
            OWNER,
            CategoryName.parse("Alquiler"),
            TransactionKind.EXPENSE,
            self.clock.now(),
        )
        self.categories.rows[self.rent.id] = self.rent

    def rule(
        self,
        starts_on: date = date(2026, 9, 18),
        amount: str = "450000.00",
        frequency: Frequency = Frequency.MONTHLY,
    ) -> RuleInput:
        return RuleInput(
            account_id=self.account_id,
            kind=TransactionKind.EXPENSE,
            amount=Decimal(amount),
            category_id=self.rent.id,
            frequency=frequency,
            starts_on=starts_on,
            description="Alquiler",
        )

    def generated_rows(self) -> list[tuple[int, date, Money]]:
        return sorted(
            (row.recurrence.number, row.occurred_on, row.money)
            for row in self.transactions.rows.values()
            if row.recurrence is not None
        )


@pytest.fixture
def setup() -> Setup:
    return Setup()


async def test_a_rule_that_starts_today_brings_its_first_time(setup: Setup) -> None:
    view = await setup.unit.create_rule.execute(OWNER, setup.rule())

    assert setup.generated_rows() == [(1, date(2026, 9, 18), ars("450000.00"))]
    assert setup.audit.actions == [AuditAction.REGISTERED]
    assert setup.db.commits == 1
    assert view.generated == 1
    assert view.next is not None
    assert view.next.on == date(2026, 10, 18)
    created = next(iter(setup.transactions.rows.values()))
    assert created.description is not None
    assert created.description.value == "Alquiler"


async def test_a_rule_that_started_months_ago_brings_what_is_due(setup: Setup) -> None:
    await setup.unit.create_rule.execute(OWNER, setup.rule(starts_on=date(2026, 6, 30)))

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


async def test_a_rule_that_starts_later_brings_nothing_yet(setup: Setup) -> None:
    view = await setup.unit.create_rule.execute(OWNER, setup.rule(starts_on=date(2026, 10, 1)))

    assert setup.generated_rows() == []
    assert view.generated == 0
    assert view.next is not None
    assert view.next.on == date(2026, 10, 1)


async def test_the_due_ones_are_generated_when_their_day_comes_and_only_once(setup: Setup) -> None:
    await setup.unit.create_rule.execute(
        OWNER, setup.rule(frequency=Frequency.WEEKLY, amount="30000.00")
    )

    assert await setup.unit.generate_due_recurring.execute(OWNER) == []
    setup.clock.advance(days=14)
    created = await setup.unit.generate_due_recurring.execute(OWNER)
    again = await setup.unit.generate_due_recurring.execute(OWNER)

    assert [row.recurrence.number for row in created if row.recurrence] == [2, 3]
    assert again == []
    assert len(setup.generated_rows()) == 3


async def test_a_deleted_time_is_not_generated_again(setup: Setup) -> None:
    await setup.unit.create_rule.execute(OWNER, setup.rule())
    first = next(iter(setup.transactions.rows.values()))

    await setup.unit.delete.execute(OWNER, first.id)
    await setup.unit.generate_due_recurring.execute(OWNER)
    [view] = await setup.unit.list_rules.execute(OWNER)

    assert len(setup.generated_rows()) == 1
    assert view.generated == 1


async def test_a_new_amount_counts_from_the_next_time_and_not_before(setup: Setup) -> None:
    view = await setup.unit.create_rule.execute(OWNER, setup.rule())
    # Pasaron dos meses sin abrir la app, y recién ahora se carga el aumento.
    setup.clock.advance(days=61)

    changed = await setup.unit.change_rule.execute(
        OWNER, view.rule.id, RuleChange(Decimal("520000.00"), "Alquiler con aumento")
    )
    setup.clock.advance(days=31)
    await setup.unit.generate_due_recurring.execute(OWNER)

    assert changed.rule.money == ars("520000.00")
    assert setup.generated_rows() == [
        (1, date(2026, 9, 18), ars("450000.00")),
        (2, date(2026, 10, 18), ars("450000.00")),
        (3, date(2026, 11, 18), ars("450000.00")),
        (4, date(2026, 12, 18), ars("520000.00")),
    ]
    assert changed.generated == 3


async def test_a_change_is_validated_before_anything_is_generated(setup: Setup) -> None:
    view = await setup.unit.create_rule.execute(OWNER, setup.rule())
    setup.clock.advance(days=31)

    with pytest.raises(AmountTooPreciseError):
        await setup.unit.change_rule.execute(OWNER, view.rule.id, RuleChange(Decimal("1.001")))

    assert len(setup.generated_rows()) == 1
    assert setup.db.commits == 1


async def test_a_cancelled_rule_keeps_what_passed_and_generates_nothing_else(
    setup: Setup,
) -> None:
    view = await setup.unit.create_rule.execute(OWNER, setup.rule())

    cancelled = await setup.unit.cancel_rule.execute(OWNER, view.rule.id)
    again = await setup.unit.cancel_rule.execute(OWNER, view.rule.id)
    setup.clock.advance(days=90)
    await setup.unit.generate_due_recurring.execute(OWNER)

    assert cancelled.rule.is_cancelled
    assert cancelled.next is None
    assert again.rule.cancelled_at == cancelled.rule.cancelled_at
    assert len(setup.generated_rows()) == 1
    with pytest.raises(RecurringRuleCancelledError):
        await setup.unit.change_rule.execute(OWNER, view.rule.id, RuleChange(Decimal("1.00")))


async def test_an_archived_account_receives_nothing_while_it_stays_archived(
    setup: Setup,
) -> None:
    await setup.unit.create_rule.execute(OWNER, setup.rule())
    setup.accounts.add(setup.account_id, OWNER, archived=True)
    setup.clock.advance(days=31)

    await setup.unit.generate_due_recurring.execute(OWNER)

    assert len(setup.generated_rows()) == 1


async def test_a_new_rule_needs_an_active_account_of_its_owner(setup: Setup) -> None:
    with pytest.raises(TransactionAccountNotFoundError):
        await setup.unit.create_rule.execute(STRANGER, setup.rule())
    setup.accounts.add(setup.account_id, OWNER, archived=True)
    with pytest.raises(TransactionAccountArchivedError):
        await setup.unit.create_rule.execute(OWNER, setup.rule())
    assert setup.recurring.rows == {}


async def test_the_same_key_does_not_create_two_rules(setup: Setup) -> None:
    first = await setup.unit.create_rule.execute(OWNER, setup.rule(), "clave-1")
    again = await setup.unit.create_rule.execute(OWNER, setup.rule(), "clave-1")

    assert again.rule.id == first.rule.id
    assert len(setup.recurring.rows) == 1
    assert len(setup.generated_rows()) == 1
    with pytest.raises(IdempotencyKeyReusedError):
        await setup.unit.create_rule.execute(OWNER, setup.rule(amount="1.00"), "clave-1")


async def test_someone_elses_rule_does_not_exist(setup: Setup) -> None:
    view = await setup.unit.create_rule.execute(OWNER, setup.rule())

    with pytest.raises(RecurringRuleNotFoundError):
        await setup.unit.cancel_rule.execute(STRANGER, view.rule.id)
    with pytest.raises(RecurringRuleNotFoundError):
        await setup.unit.change_rule.execute(STRANGER, view.rule.id, RuleChange(Decimal("1.00")))
    assert await setup.unit.list_rules.execute(STRANGER) == []
    assert await setup.unit.generate_due_recurring.execute(STRANGER) == []


async def test_a_category_with_a_rule_cannot_be_deleted(setup: Setup) -> None:
    view = await setup.unit.create_rule.execute(OWNER, setup.rule())
    first = next(iter(setup.transactions.rows.values()))
    await setup.unit.delete.execute(OWNER, first.id)
    await setup.unit.cancel_rule.execute(OWNER, view.rule.id)

    with pytest.raises(CategoryInUseError):
        await setup.unit.delete_category.execute(OWNER, setup.rent.id)


async def test_a_generated_time_is_edited_like_any_transaction(setup: Setup) -> None:
    await setup.unit.create_rule.execute(OWNER, setup.rule())
    first = next(iter(setup.transactions.rows.values()))

    edited = await setup.unit.edit.execute(
        OWNER,
        first.id,
        TransactionInput(
            account_id=setup.account_id,
            kind=TransactionKind.EXPENSE,
            amount=Decimal("455000.00"),
            category_id=setup.rent.id,
            occurred_on=first.occurred_on,
            description="Alquiler y expensas",
        ),
    )

    assert edited.recurrence == first.recurrence
    assert edited.money == ars("455000.00")
