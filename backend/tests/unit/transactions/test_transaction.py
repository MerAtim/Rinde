"""Reglas del movimiento (ADR-0011)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rinde.shared.domain.money import Currency, Money
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.errors import (
    CategoryKindMismatchError,
    TransactionAmountNotPositiveError,
    TransactionCurrencyMismatchError,
    TransactionDateInFutureError,
    TransactionDeletedError,
    TransactionDescriptionInvalidError,
)
from rinde.transactions.domain.transaction import (
    Description,
    Draft,
    TargetAccount,
    Transaction,
    register,
)

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)
TODAY = NOW.date()
OWNER = uuid4()
ACCOUNT = TargetAccount(id=uuid4(), currency=Currency.ARS)


def _category(kind: TransactionKind = TransactionKind.EXPENSE) -> Category:
    return Category(
        id=uuid4(),
        owner_id=OWNER,
        name=CategoryName.parse("Supermercado"),
        kind=kind,
        created_at=NOW,
    )


def _draft(
    kind: TransactionKind = TransactionKind.EXPENSE,
    money: Money | None = None,
    occurred_on: date = TODAY,
    description: str | None = None,
) -> Draft:
    return Draft(
        kind=kind,
        money=money or Money(Decimal("15300.50"), Currency.ARS),
        category=_category(kind),
        occurred_on=occurred_on,
        description=Description.parse(description),
    )


def _register(draft: Draft | None = None, account: TargetAccount = ACCOUNT) -> Transaction:
    return register(draft or _draft(), account, transaction_id=uuid4(), owner_id=OWNER, at=NOW)


def test_a_registered_expense_keeps_what_was_loaded() -> None:
    movement = _register(_draft(occurred_on=date(2026, 9, 17), description="  Coto  "))

    assert movement.money == Money(Decimal("15300.50"), Currency.ARS)
    assert movement.occurred_on == date(2026, 9, 17)
    assert movement.description == Description("Coto")
    assert movement.created_at == movement.updated_at == NOW
    assert not movement.is_deleted


def test_the_sign_comes_from_the_kind_and_the_amount_stays_positive() -> None:
    expense = _register()
    income = _register(_draft(kind=TransactionKind.INCOME))

    assert expense.money.is_positive
    assert income.money.is_positive
    assert expense.signed_amount == Money(Decimal("-15300.50"), Currency.ARS)
    assert income.signed_amount == income.money


@pytest.mark.parametrize("amount", ["0", "-0.01", "-1000"])
def test_an_amount_that_is_not_positive_is_rejected(amount: str) -> None:
    with pytest.raises(TransactionAmountNotPositiveError):
        _register(_draft(money=Money(Decimal(amount), Currency.ARS)))


def test_the_currency_has_to_be_the_one_of_the_account() -> None:
    with pytest.raises(TransactionCurrencyMismatchError):
        _register(_draft(money=Money(Decimal("100.00"), Currency.USD)))


def test_an_expense_category_does_not_classify_an_income() -> None:
    draft = Draft(
        kind=TransactionKind.INCOME,
        money=Money(Decimal("1000.00"), Currency.ARS),
        category=_category(TransactionKind.EXPENSE),
        occurred_on=TODAY,
    )

    with pytest.raises(CategoryKindMismatchError):
        _register(draft)


def test_a_date_from_the_future_is_rejected_with_one_day_of_tolerance() -> None:
    # El reloj de quien carga puede ir adelantado del UTC del servidor.
    assert _register(_draft(occurred_on=TODAY + timedelta(days=1))).occurred_on

    with pytest.raises(TransactionDateInFutureError):
        _register(_draft(occurred_on=TODAY + timedelta(days=2)))


def test_editing_replaces_the_data_and_marks_the_change() -> None:
    movement = _register()
    later = NOW + timedelta(hours=3)

    edited = movement.edited(_draft(money=Money(Decimal("2.00"), Currency.ARS)), later)

    assert edited.money == Money(Decimal("2.00"), Currency.ARS)
    assert edited.updated_at == later
    assert edited.created_at == movement.created_at
    assert edited.id == movement.id


def test_a_deleted_movement_cannot_be_edited() -> None:
    deleted = _register().deleted(NOW)

    with pytest.raises(TransactionDeletedError):
        deleted.edited(_draft(), NOW)


def test_deleting_is_idempotent_and_restoring_brings_it_back() -> None:
    movement = _register()
    later = NOW + timedelta(minutes=5)

    deleted = movement.deleted(NOW)
    assert deleted.deleted_at == NOW
    assert deleted.deleted(later) is deleted

    restored = deleted.restored(later)
    assert not restored.is_deleted
    assert restored.updated_at == later


@pytest.mark.parametrize("raw", ["x" * 121, "Coto\u200bexpress", "Coto\nexpress"])
def test_an_invalid_description_is_rejected(raw: str) -> None:
    with pytest.raises(TransactionDescriptionInvalidError):
        Description.parse(raw)


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_an_empty_description_is_no_description(raw: str | None) -> None:
    assert Description.parse(raw) is None


@given(
    amount=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("9999999999.99"), places=2),
    kind=st.sampled_from(TransactionKind),
)
def test_the_signed_amount_always_has_the_size_of_the_loaded_one(
    amount: Decimal, kind: TransactionKind
) -> None:
    movement = _register(_draft(kind=kind, money=Money(amount, Currency.ARS)))

    signed = movement.signed_amount
    assert abs(signed.amount) == amount
    assert (signed.amount > 0) is (kind is TransactionKind.INCOME)
