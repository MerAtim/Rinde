"""La regla recurrente: fechas, qué venció y qué se puede cambiar (ADR-0027)."""

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
    RecurringRuleCancelledError,
    RecurringStartOutOfRangeError,
    TransactionAccountArchivedError,
    TransactionAmountNotPositiveError,
    TransactionCurrencyMismatchError,
)
from rinde.transactions.domain.recurring import (
    Frequency,
    RecurringRule,
    RuleDraft,
    occurrence_on,
    recurring_rule,
)
from rinde.transactions.domain.transaction import Description, TargetAccount

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)
TODAY = date(2026, 9, 18)
OWNER = uuid4()
ACCOUNT = TargetAccount(id=uuid4(), currency=Currency.ARS)


def ars(amount: str) -> Money:
    return Money(Decimal(amount), Currency.ARS)


def _category(kind: TransactionKind = TransactionKind.EXPENSE) -> Category:
    return Category(uuid4(), OWNER, CategoryName.parse("Alquiler"), kind, NOW)


def _rule(
    frequency: Frequency = Frequency.MONTHLY,
    starts_on: date = date(2026, 7, 31),
    kind: TransactionKind = TransactionKind.EXPENSE,
) -> RecurringRule:
    return recurring_rule(
        RuleDraft(kind, ars("450000.00"), _category(kind), frequency, starts_on),
        ACCOUNT,
        rule_id=uuid4(),
        owner_id=OWNER,
        at=NOW,
    )


@pytest.mark.parametrize(
    ("frequency", "expected"),
    [
        (Frequency.WEEKLY, [date(2026, 7, 31), date(2026, 8, 7), date(2026, 8, 14)]),
        (Frequency.MONTHLY, [date(2026, 7, 31), date(2026, 8, 31), date(2026, 9, 30)]),
        (Frequency.YEARLY, [date(2026, 7, 31), date(2027, 7, 31), date(2028, 7, 31)]),
    ],
    ids=["semanal", "mensual", "anual"],
)
def test_each_time_is_counted_from_the_first(frequency: Frequency, expected: list[date]) -> None:
    first = date(2026, 7, 31)

    assert [occurrence_on(first, frequency, number) for number in (1, 2, 3)] == expected


def test_a_31_comes_back_after_a_short_month() -> None:
    assert occurrence_on(date(2026, 8, 31), Frequency.MONTHLY, 3) == date(2026, 10, 31)


def test_a_29_of_february_falls_on_the_28_in_a_common_year() -> None:
    assert occurrence_on(date(2028, 2, 29), Frequency.YEARLY, 2) == date(2029, 2, 28)


def test_only_what_already_arrived_is_due() -> None:
    rent = _rule()

    assert [(item.number, item.on) for item in rent.due(0, TODAY)] == [
        (1, date(2026, 7, 31)),
        (2, date(2026, 8, 31)),
    ]
    assert rent.next(2) is not None
    assert rent.next(2) == rent.occurrence(3)


def test_it_continues_after_the_last_one_generated() -> None:
    rent = _rule()

    assert [item.number for item in rent.due(1, TODAY)] == [2]
    assert rent.due(2, TODAY) == []


def test_a_rule_that_starts_later_has_nothing_due_yet() -> None:
    salary = _rule(starts_on=date(2026, 10, 1), kind=TransactionKind.INCOME)

    assert salary.due(0, TODAY) == []
    assert salary.next(0) == salary.occurrence(1)


@given(st.sampled_from(Frequency), st.integers(min_value=0, max_value=60))
def test_the_due_ones_are_consecutive_and_none_is_after_today(
    frequency: Frequency, days_later: int
) -> None:
    today = TODAY + timedelta(days=days_later)

    due = _rule(frequency).due(0, today)

    assert [item.number for item in due] == list(range(1, len(due) + 1))
    assert all(item.on <= today for item in due)
    assert _rule(frequency).occurrence(len(due) + 1).on > today


def test_a_cancelled_rule_generates_nothing_more() -> None:
    rent = _rule().cancelled(NOW)

    assert rent.due(0, TODAY) == []
    assert rent.next(0) is None
    assert rent.cancelled(NOW + timedelta(days=1)).cancelled_at == NOW


def test_changing_the_amount_keeps_the_rest() -> None:
    rent = _rule()

    changed = rent.changed(ars("520000.00"), Description.parse("Alquiler con aumento"))

    assert changed.money == ars("520000.00")
    assert changed.description == Description.parse("Alquiler con aumento")
    assert (changed.starts_on, changed.frequency, changed.id) == (
        rent.starts_on,
        rent.frequency,
        rent.id,
    )


def test_what_cannot_be_changed() -> None:
    rent = _rule()

    with pytest.raises(TransactionAmountNotPositiveError):
        rent.changed(ars("0.00"), None)
    with pytest.raises(TransactionCurrencyMismatchError):
        rent.changed(Money(Decimal("300.00"), Currency.USD), None)
    with pytest.raises(RecurringRuleCancelledError):
        rent.cancelled(NOW).changed(ars("1.00"), None)


@pytest.mark.parametrize(
    "starts_on",
    [date(2025, 9, 18), date(2027, 9, 18)],
    ids=["un año antes", "un año después"],
)
def test_the_first_time_can_be_up_to_a_year_away(starts_on: date) -> None:
    assert _rule(starts_on=starts_on).starts_on == starts_on


@pytest.mark.parametrize(
    "starts_on",
    [date(2025, 9, 17), date(2027, 9, 19)],
    ids=["más de un año antes", "más de un año después"],
)
def test_a_first_time_further_away_is_rejected(starts_on: date) -> None:
    with pytest.raises(RecurringStartOutOfRangeError):
        _rule(starts_on=starts_on)


def test_the_rules_of_a_transaction_apply() -> None:
    draft = RuleDraft(TransactionKind.EXPENSE, ars("1.00"), _category(), Frequency.MONTHLY, TODAY)

    with pytest.raises(TransactionAccountArchivedError):
        recurring_rule(
            draft,
            TargetAccount(ACCOUNT.id, Currency.ARS, is_archived=True),
            rule_id=uuid4(),
            owner_id=OWNER,
            at=NOW,
        )
    with pytest.raises(TransactionCurrencyMismatchError):
        recurring_rule(
            draft,
            TargetAccount(ACCOUNT.id, Currency.USD),
            rule_id=uuid4(),
            owner_id=OWNER,
            at=NOW,
        )
    with pytest.raises(CategoryKindMismatchError):
        recurring_rule(
            RuleDraft(TransactionKind.INCOME, ars("1.00"), _category(), Frequency.MONTHLY, TODAY),
            ACCOUNT,
            rule_id=uuid4(),
            owner_id=OWNER,
            at=NOW,
        )


def test_each_time_is_a_transaction_like_the_rule() -> None:
    rent = _rule()
    category = _category()

    draft = rent.draft(rent.occurrence(2), category)

    assert (draft.kind, draft.money, draft.occurred_on, draft.category) == (
        TransactionKind.EXPENSE,
        rent.money,
        date(2026, 8, 31),
        category,
    )
