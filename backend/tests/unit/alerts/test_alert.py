"""Reglas de la alerta de presupuesto (ADR-0022)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from rinde.alerts.domain.alert import BudgetAlert, Threshold, due_threshold
from rinde.shared.domain.money import Currency, Money

WARNING = Threshold.WARNING
OVER = Threshold.OVER


@pytest.mark.parametrize(
    ("reached", "raised", "due"),
    [
        (None, set(), None),
        (WARNING, set(), WARNING),
        (WARNING, {WARNING}, None),
        (OVER, set(), OVER),
        (OVER, {WARNING}, OVER),
        (OVER, {OVER}, None),
        # Después del 100 %, bajar al 85 % no avisa el 80 %: el aviso fuerte ya lo incluía.
        (WARNING, {OVER}, None),
        (None, {WARNING, OVER}, None),
    ],
)
def test_the_due_threshold(
    reached: Threshold | None, raised: set[Threshold], due: Threshold | None
) -> None:
    assert due_threshold(reached, raised) is due


def _alert(**changes: object) -> BudgetAlert:
    values: dict[str, object] = {
        "id": uuid4(),
        "owner_id": uuid4(),
        "category_id": uuid4(),
        "month": date(2026, 11, 1),
        "threshold": WARNING,
        "limit": Money(Decimal("1000.00"), Currency.ARS),
        "spent": Money(Decimal("850.00"), Currency.ARS),
        "raised_at": datetime(2026, 11, 10, 15, tzinfo=UTC),
    }
    values.update(changes)
    return BudgetAlert(**values)  # type: ignore[arg-type]


def test_an_alert_starts_unread() -> None:
    alert = _alert()

    assert not alert.is_read
    assert _alert(read_at=datetime(2026, 11, 11, tzinfo=UTC)).is_read


def test_the_month_of_an_alert_is_its_first_day() -> None:
    with pytest.raises(ValueError, match="primer día"):
        _alert(month=date(2026, 11, 10))


def test_spent_is_in_the_currency_of_the_limit() -> None:
    with pytest.raises(ValueError, match="moneda del tope"):
        _alert(spent=Money(Decimal("1.00"), Currency.USD))
