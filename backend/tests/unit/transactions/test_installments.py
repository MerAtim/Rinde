"""El plan de cuotas: reparto exacto, fechas y cuándo vence cada una (ADR-0026)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rinde.shared.domain.money import Currency, Money
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.errors import (
    CategoryKindMismatchError,
    InstallmentAmountTooSmallError,
    InstallmentCountInvalidError,
    TransactionAccountArchivedError,
    TransactionAmountNotPositiveError,
    TransactionCurrencyMismatchError,
    TransactionDateInFutureError,
)
from rinde.transactions.domain.installments import InstallmentPlan, PlanDraft, due_on, plan
from rinde.transactions.domain.transaction import TargetAccount

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)
OWNER = uuid4()
ACCOUNT = TargetAccount(id=uuid4(), currency=Currency.ARS)


def ars(amount: str) -> Money:
    return Money(Decimal(amount), Currency.ARS)


def _category(kind: TransactionKind = TransactionKind.EXPENSE) -> Category:
    return Category(uuid4(), OWNER, CategoryName.parse("Electro"), kind, NOW)


def _plan(
    total: str = "100.00", count: int = 3, first_on: date = date(2026, 8, 31)
) -> InstallmentPlan:
    return plan(
        PlanDraft(ars(total), count, _category(), first_on),
        ACCOUNT,
        plan_id=uuid4(),
        owner_id=OWNER,
        at=NOW,
    )


def test_the_installments_add_up_to_the_total_and_the_first_ones_carry_the_cents() -> None:
    schedule = _plan("100.00", 3).schedule()

    assert [item.money for item in schedule] == [ars("33.34"), ars("33.33"), ars("33.33")]
    assert [item.number for item in schedule] == [1, 2, 3]


def test_each_installment_falls_the_same_day_of_the_next_month() -> None:
    schedule = _plan(first_on=date(2025, 12, 15)).schedule()

    assert [item.due_on for item in schedule] == [
        date(2025, 12, 15),
        date(2026, 1, 15),
        date(2026, 2, 15),
    ]


@pytest.mark.parametrize(
    ("first", "number", "expected"),
    [
        (date(2026, 8, 31), 2, date(2026, 9, 30)),
        (date(2027, 1, 31), 2, date(2027, 2, 28)),
        (date(2028, 1, 31), 2, date(2028, 2, 29)),
        (date(2026, 8, 31), 3, date(2026, 10, 31)),
    ],
    ids=["31 en septiembre", "febrero", "febrero bisiesto", "vuelve al 31"],
)
def test_a_day_the_month_does_not_have_falls_on_its_last_day(
    first: date, number: int, expected: date
) -> None:
    assert due_on(first, number) == expected


def test_only_what_already_arrived_is_due() -> None:
    purchase = _plan(first_on=date(2026, 8, 31))

    assert [item.number for item in purchase.due(date(2026, 9, 29))] == [1]
    assert [item.number for item in purchase.due(date(2026, 9, 30))] == [1, 2]


def test_a_cancelled_plan_is_not_due_anymore() -> None:
    purchase = _plan().cancelled(NOW)

    assert purchase.due(date(2027, 1, 1)) == []
    assert purchase.cancelled(datetime(2026, 10, 1, tzinfo=UTC)).cancelled_at == NOW


def test_an_installment_is_drafted_as_a_plain_expense() -> None:
    category = _category()
    purchase = _plan()
    first = purchase.schedule()[0]

    draft = purchase.draft(first, category)

    assert draft.kind is TransactionKind.EXPENSE
    assert draft.money == first.money
    assert draft.occurred_on == first.due_on


@pytest.mark.parametrize("count", [1, 49, 0])
def test_from_two_to_forty_eight_installments(count: int) -> None:
    with pytest.raises(InstallmentCountInvalidError):
        _plan(count=count)


def test_every_installment_is_at_least_one_cent() -> None:
    assert len(_plan("0.03", 3).schedule()) == 3
    with pytest.raises(InstallmentAmountTooSmallError):
        _plan("0.02", 3)


def test_the_total_is_positive() -> None:
    with pytest.raises(TransactionAmountNotPositiveError):
        _plan("0.00")


def test_a_plan_follows_the_rules_of_an_expense() -> None:
    def attempt(
        account: TargetAccount = ACCOUNT,
        category: Category | None = None,
        first_on: date = date(2026, 9, 1),
        total: Money | None = None,
    ) -> None:
        plan(
            PlanDraft(total or ars("10.00"), 2, category or _category(), first_on),
            account,
            plan_id=uuid4(),
            owner_id=OWNER,
            at=NOW,
        )

    with pytest.raises(TransactionAccountArchivedError):
        attempt(account=TargetAccount(uuid4(), Currency.ARS, is_archived=True))
    with pytest.raises(TransactionCurrencyMismatchError):
        attempt(total=Money(Decimal("10.00"), Currency.USD))
    with pytest.raises(CategoryKindMismatchError):
        attempt(category=_category(TransactionKind.INCOME))
    with pytest.raises(TransactionDateInFutureError):
        attempt(first_on=date(2026, 9, 20))


@given(
    st.decimals(min_value=Decimal("0.48"), max_value=Decimal("100000000"), places=2),
    st.integers(min_value=2, max_value=48),
)
def test_the_schedule_always_closes_with_the_total(total: Decimal, count: int) -> None:
    schedule = _plan(str(total), count).schedule()

    assert Money.total((item.money for item in schedule), Currency.ARS) == ars(str(total))
