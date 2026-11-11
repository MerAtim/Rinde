"""El resumen del libro para el dashboard, sobre puertos en memoria (ADR-0018)."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from rinde.shared.domain.money import Currency, Money
from rinde.transactions.application.ports import BalanceChange, LedgerScope
from rinde.transactions.application.use_cases import TransactionInput, TransferInput
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from tests.unit.transactions.fakes import Harness

pytestmark = pytest.mark.anyio

OWNER = uuid4()
SCOPE = LedgerScope(since=date(2026, 9, 1), until=date(2026, 9, 30))


def _ars(amount: str) -> Money:
    return Money(Decimal(amount), Currency.ARS)


def _category(harness: Harness, kind: TransactionKind, name: str) -> Category:
    category = Category(
        id=uuid4(),
        owner_id=OWNER,
        name=CategoryName.parse(name),
        kind=kind,
        created_at=harness.clock.now(),
        slug="groceries" if kind is TransactionKind.EXPENSE else None,
    )
    harness.categories.rows[category.id] = category
    return category


def _account(harness: Harness) -> UUID:
    account_id = uuid4()
    harness.accounts.add(account_id, OWNER, Currency.ARS)
    return account_id


async def _move(
    harness: Harness, account_id: UUID, category: Category, amount: str, day: date
) -> None:
    await harness.unit.register.execute(
        OWNER,
        TransactionInput(
            account_id=account_id,
            kind=category.kind,
            amount=Decimal(amount),
            category_id=category.id,
            occurred_on=day,
        ),
    )


async def test_flows_are_daily_totals_by_category_without_transfers() -> None:
    harness = Harness()
    bank, cash = _account(harness), _account(harness)
    food = _category(harness, TransactionKind.EXPENSE, "Súper")
    salary = _category(harness, TransactionKind.INCOME, "Sueldo")
    await _move(harness, bank, salary, "1000.00", date(2026, 9, 1))
    await _move(harness, bank, food, "10.00", date(2026, 9, 5))
    await _move(harness, cash, food, "5.00", date(2026, 9, 5))
    await _move(harness, bank, food, "99.00", date(2026, 8, 31))
    await harness.unit.register_transfer.execute(
        OWNER,
        TransferInput(
            from_account_id=bank,
            to_account_id=cash,
            sent=Decimal("200.00"),
            received=Decimal("200.00"),
            occurred_on=date(2026, 9, 5),
        ),
    )

    summary = await harness.unit.summary.execute(OWNER, SCOPE)

    flows = sorted((f.day, f.kind, f.category_name, f.total) for f in summary.flows)
    assert flows == [
        (date(2026, 9, 1), TransactionKind.INCOME, "Sueldo", _ars("1000.00")),
        (date(2026, 9, 5), TransactionKind.EXPENSE, "Súper", _ars("15.00")),
    ]
    assert {f.category_slug for f in summary.flows} == {None, "groceries"}


async def test_balance_changes_join_movements_and_transfers_with_an_opening() -> None:
    harness = Harness()
    bank, cash = _account(harness), _account(harness)
    food = _category(harness, TransactionKind.EXPENSE, "Súper")
    salary = _category(harness, TransactionKind.INCOME, "Sueldo")
    await _move(harness, bank, salary, "1000.00", date(2026, 8, 1))
    await _move(harness, bank, food, "10.00", date(2026, 9, 5))
    await harness.unit.register_transfer.execute(
        OWNER,
        TransferInput(
            from_account_id=bank,
            to_account_id=cash,
            sent=Decimal("200.00"),
            received=Decimal("200.00"),
            occurred_on=date(2026, 9, 5),
        ),
    )

    summary = await harness.unit.summary.execute(OWNER, SCOPE)

    assert sorted(
        summary.balance_changes, key=lambda c: (str(c.account_id), str(c.month))
    ) == sorted(
        [
            BalanceChange(bank, None, _ars("1000.00")),
            BalanceChange(bank, date(2026, 9, 1), _ars("-210.00")),
            BalanceChange(cash, date(2026, 9, 1), _ars("200.00")),
        ],
        key=lambda c: (str(c.account_id), str(c.month)),
    )


async def test_choosing_an_account_counts_only_its_side_of_a_transfer() -> None:
    harness = Harness()
    bank, cash = _account(harness), _account(harness)
    await harness.unit.register_transfer.execute(
        OWNER,
        TransferInput(
            from_account_id=bank,
            to_account_id=cash,
            sent=Decimal("200.00"),
            received=Decimal("200.00"),
            occurred_on=date(2026, 9, 5),
        ),
    )

    summary = await harness.unit.summary.execute(
        OWNER, LedgerScope(SCOPE.since, SCOPE.until, frozenset({bank}))
    )

    assert summary.balance_changes == [BalanceChange(bank, date(2026, 9, 1), _ars("-200.00"))]


async def test_nothing_of_someone_else_is_summarized() -> None:
    harness = Harness()
    bank = _account(harness)
    salary = _category(harness, TransactionKind.INCOME, "Sueldo")
    await _move(harness, bank, salary, "1000.00", date(2026, 9, 1))

    summary = await harness.unit.summary.execute(uuid4(), SCOPE)

    assert summary.flows == []
    assert summary.balance_changes == []


async def test_flows_in_the_reference_currency_come_by_month() -> None:
    harness = Harness()
    bank = _account(harness)
    food = _category(harness, TransactionKind.EXPENSE, "Súper")
    await _move(harness, bank, food, "10.00", date(2026, 9, 5))
    await _move(harness, bank, food, "5.00", date(2026, 9, 17))

    summary = await harness.unit.summary.execute(
        OWNER, LedgerScope(SCOPE.since, SCOPE.until, monthly_currency=Currency.ARS)
    )
    daily = await harness.unit.summary.execute(
        OWNER, LedgerScope(SCOPE.since, SCOPE.until, monthly_currency=Currency.USD)
    )

    assert [(f.day, f.total) for f in summary.flows] == [(date(2026, 9, 1), _ars("15.00"))]
    assert len(daily.flows) == 2
