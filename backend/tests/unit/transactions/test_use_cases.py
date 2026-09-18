"""Casos de uso de movimientos, con fakes en memoria (ADR-0011)."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from rinde.shared.domain.money import AmountTooPreciseError, Currency, Money
from rinde.transactions.application.ports import AccountBalance, TransactionFilters
from rinde.transactions.application.use_cases import TransactionInput
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.errors import (
    CategoryKindMismatchError,
    CategoryNotFoundError,
    IdempotencyKeyReusedError,
    TransactionAccountArchivedError,
    TransactionAccountNotFoundError,
    TransactionCurrencyMismatchError,
    TransactionNotFoundError,
)
from rinde.transactions.domain.transaction import AuditAction
from tests.unit.transactions.fakes import Harness, a_date

pytestmark = pytest.mark.anyio

OWNER = uuid4()
STRANGER = uuid4()


class Setup(Harness):
    """Un dueño con una cuenta en pesos y dos categorías."""

    def __init__(self) -> None:
        super().__init__()
        self.account_id = uuid4()
        self.accounts.add(self.account_id, OWNER)
        self.expense_category = self._category(TransactionKind.EXPENSE, "Supermercado")
        self.income_category = self._category(TransactionKind.INCOME, "Sueldo")

    def _category(self, kind: TransactionKind, name: str) -> Category:
        category = Category(
            id=uuid4(),
            owner_id=OWNER,
            name=CategoryName.parse(name),
            kind=kind,
            created_at=self.clock.now(),
        )
        self.categories.rows[category.id] = category
        return category

    def an_input(
        self,
        amount: str = "15300.50",
        kind: TransactionKind = TransactionKind.EXPENSE,
        category_id: UUID | None = None,
        account_id: UUID | None = None,
        day: int = 18,
    ) -> TransactionInput:
        by_kind = self.expense_category if kind is TransactionKind.EXPENSE else self.income_category
        return TransactionInput(
            account_id=account_id or self.account_id,
            kind=kind,
            amount=Decimal(amount),
            category_id=category_id or by_kind.id,
            occurred_on=a_date(day),
        )


@pytest.fixture
def setup() -> Setup:
    return Setup()


async def test_registering_an_expense_saves_it_and_leaves_audit(setup: Setup) -> None:
    movement = await setup.unit.register.execute(OWNER, setup.an_input())

    assert movement.money == Money(Decimal("15300.50"), Currency.ARS)
    assert setup.transactions.rows[movement.id] == movement
    assert setup.audit.actions == [AuditAction.REGISTERED]
    assert setup.db.commits == 1


async def test_a_movement_in_an_account_that_is_not_mine_is_not_found(setup: Setup) -> None:
    with pytest.raises(TransactionAccountNotFoundError):
        await setup.unit.register.execute(STRANGER, setup.an_input())


async def test_an_archived_account_does_not_take_new_movements(setup: Setup) -> None:
    archived = uuid4()
    setup.accounts.add(archived, OWNER, archived=True)

    with pytest.raises(TransactionAccountArchivedError):
        await setup.unit.register.execute(OWNER, setup.an_input(account_id=archived))


async def test_a_category_from_another_person_is_not_found(setup: Setup) -> None:
    foreign = Category(
        id=uuid4(),
        owner_id=STRANGER,
        name=CategoryName.parse("Ajena"),
        kind=TransactionKind.EXPENSE,
        created_at=setup.clock.now(),
    )
    setup.categories.rows[foreign.id] = foreign

    with pytest.raises(CategoryNotFoundError):
        await setup.unit.register.execute(OWNER, setup.an_input(category_id=foreign.id))


async def test_an_income_needs_an_income_category(setup: Setup) -> None:
    with pytest.raises(CategoryKindMismatchError):
        await setup.unit.register.execute(
            OWNER,
            setup.an_input(kind=TransactionKind.INCOME, category_id=setup.expense_category.id),
        )


async def test_an_amount_with_more_decimals_than_the_currency_is_rejected(setup: Setup) -> None:
    with pytest.raises(AmountTooPreciseError):
        await setup.unit.register.execute(OWNER, setup.an_input(amount="10.999"))


async def test_the_same_key_with_the_same_request_does_not_duplicate(setup: Setup) -> None:
    data = setup.an_input()

    first = await setup.unit.register.execute(OWNER, data, "clave-1")
    second = await setup.unit.register.execute(OWNER, data, "clave-1")

    assert first.id == second.id
    assert len(setup.transactions.rows) == 1
    assert setup.audit.actions == [AuditAction.REGISTERED]


async def test_the_same_key_with_another_request_is_an_error(setup: Setup) -> None:
    await setup.unit.register.execute(OWNER, setup.an_input(), "clave-1")

    with pytest.raises(IdempotencyKeyReusedError):
        await setup.unit.register.execute(OWNER, setup.an_input(amount="20.00"), "clave-1")


async def test_two_equal_expenses_without_key_are_two_movements(setup: Setup) -> None:
    await setup.unit.register.execute(OWNER, setup.an_input(amount="1500.00"))
    await setup.unit.register.execute(OWNER, setup.an_input(amount="1500.00"))

    assert len(setup.transactions.rows) == 2


async def test_editing_changes_the_data_and_leaves_audit(setup: Setup) -> None:
    movement = await setup.unit.register.execute(OWNER, setup.an_input())

    edited = await setup.unit.edit.execute(OWNER, movement.id, setup.an_input(amount="900.00"))

    assert edited.money == Money(Decimal("900.00"), Currency.ARS)
    assert setup.audit.actions == [AuditAction.REGISTERED, AuditAction.EDITED]


async def test_editing_a_movement_of_another_person_is_not_found(setup: Setup) -> None:
    movement = await setup.unit.register.execute(OWNER, setup.an_input())

    with pytest.raises(TransactionNotFoundError):
        await setup.unit.edit.execute(STRANGER, movement.id, setup.an_input())


async def test_the_currency_of_the_account_cannot_be_dodged_when_editing(setup: Setup) -> None:
    dollars = uuid4()
    setup.accounts.add(dollars, OWNER, Currency.USD)
    movement = await setup.unit.register.execute(OWNER, setup.an_input())
    # La cuenta del movimiento sigue siendo la de pesos: un monto en dólares no entra.
    setup.accounts.accounts[(setup.account_id, OWNER)] = setup.accounts.accounts[(dollars, OWNER)]

    with pytest.raises(TransactionCurrencyMismatchError):
        await setup.unit.edit.execute(OWNER, movement.id, setup.an_input(amount="10.00"))


async def test_a_deleted_movement_leaves_the_balance_and_can_be_restored(setup: Setup) -> None:
    movement = await setup.unit.register.execute(OWNER, setup.an_input(amount="1000.00"))

    await setup.unit.delete.execute(OWNER, movement.id)
    assert await setup.unit.balances.execute(OWNER) == []
    with pytest.raises(TransactionNotFoundError):
        await setup.unit.get.execute(OWNER, movement.id)

    restored = await setup.unit.restore.execute(OWNER, movement.id)
    assert not restored.is_deleted
    assert setup.audit.actions[-2:] == [AuditAction.DELETED, AuditAction.RESTORED]


async def test_the_balance_adds_incomes_and_subtracts_expenses(setup: Setup) -> None:
    await setup.unit.register.execute(
        OWNER, setup.an_input(amount="100000.00", kind=TransactionKind.INCOME)
    )
    await setup.unit.register.execute(OWNER, setup.an_input(amount="15300.50"))

    balances = await setup.unit.balances.execute(OWNER)

    assert balances == [AccountBalance(setup.account_id, Money(Decimal("84699.50"), Currency.ARS))]


async def test_the_list_pages_by_cursor_without_repeating(setup: Setup) -> None:
    for day in (15, 16, 17, 18):
        await setup.unit.register.execute(OWNER, setup.an_input(day=day))

    first = await setup.unit.list.execute(OWNER, TransactionFilters(), limit=3)
    second = await setup.unit.list.execute(
        OWNER, TransactionFilters(), cursor=first.next_cursor, limit=3
    )

    assert [row.occurred_on.day for row in first.items] == [18, 17, 16]
    assert [row.occurred_on.day for row in second.items] == [15]
    assert second.next_cursor is None


async def test_the_list_only_brings_what_is_asked(setup: Setup) -> None:
    other_account = uuid4()
    setup.accounts.add(other_account, OWNER)
    await setup.unit.register.execute(OWNER, setup.an_input(day=15))
    await setup.unit.register.execute(OWNER, setup.an_input(day=18, account_id=other_account))

    page = await setup.unit.list.execute(
        OWNER, TransactionFilters(account_id=other_account, since=a_date(16))
    )

    assert [row.account_id for row in page.items] == [other_account]


async def test_nobody_sees_the_movements_of_another_person(setup: Setup) -> None:
    await setup.unit.register.execute(OWNER, setup.an_input())

    page = await setup.unit.list.execute(STRANGER, TransactionFilters())

    assert page.items == []
    assert await setup.unit.balances.execute(STRANGER) == []
