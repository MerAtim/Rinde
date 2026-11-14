"""Movimientos recurrentes: una regla que se vuelve movimientos de a uno (ADR-0027).

El alquiler, el sueldo, una suscripción. Cada vez se vuelve movimiento recién
cuando llega su fecha, como las cuotas (ADR-0026): ningún movimiento tiene
fecha futura, y todo lo que lee movimientos sigue viendo solo lo que pasó.
"""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from rinde.shared.domain.calendar import add_months, argentine_day
from rinde.shared.domain.money import Money
from rinde.transactions.domain.category import Category, TransactionKind
from rinde.transactions.domain.errors import (
    CategoryKindMismatchError,
    RecurringRuleCancelledError,
    RecurringStartOutOfRangeError,
    TransactionAccountArchivedError,
    TransactionAmountNotPositiveError,
    TransactionCurrencyMismatchError,
)
from rinde.transactions.domain.transaction import Description, Draft, TargetAccount


class Frequency(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


_MONTHS_PER_STEP = {Frequency.MONTHLY: 1, Frequency.YEARLY: 12}


def occurrence_on(first: date, frequency: Frequency, number: int) -> date:
    """La vez `number` (desde 1), contada siempre desde la primera (ADR-0027).

    Mensual y anual caen el mismo día; si el mes no lo tiene, el último.
    """
    if frequency is Frequency.WEEKLY:
        return first + timedelta(weeks=number - 1)
    return add_months(first, _MONTHS_PER_STEP[frequency] * (number - 1))


@dataclass(frozen=True, slots=True)
class Occurrence:
    number: int
    on: date


@dataclass(frozen=True, slots=True)
class RecurringRule:
    START_RANGE_MONTHS: ClassVar[int] = 12
    """La primera vez, como mucho un año antes o un año después de hoy."""

    id: UUID
    owner_id: UUID
    account_id: UUID
    kind: TransactionKind
    category_id: UUID
    money: Money
    frequency: Frequency
    starts_on: date
    created_at: datetime
    description: Description | None = None
    cancelled_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.money.is_positive:
            raise TransactionAmountNotPositiveError

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled_at is not None

    def occurrence(self, number: int) -> Occurrence:
        return Occurrence(number, occurrence_on(self.starts_on, self.frequency, number))

    def due(self, last_generated: int, today: date) -> list[Occurrence]:
        """Las que llegaron después de la última generada. Una cancelada no genera más.

        `last_generated` es el número más alto que ya es movimiento, borrados
        incluidos: se sigue desde ahí sin recorrer toda la historia.
        """
        if self.is_cancelled:
            return []
        return list(self._until(last_generated + 1, today))

    def next(self, last_generated: int) -> Occurrence | None:
        """La próxima que se va a generar, o nada si se canceló."""
        return None if self.is_cancelled else self.occurrence(last_generated + 1)

    def draft(self, occurrence: Occurrence, category: Category) -> Draft:
        return Draft(
            kind=self.kind,
            money=self.money,
            category=category,
            occurred_on=occurrence.on,
            description=self.description,
        )

    def changed(self, money: Money, description: Description | None) -> RecurringRule:
        """El monto nuevo vale para lo que todavía no se generó (ADR-0027, decisión 5)."""
        if self.is_cancelled:
            raise RecurringRuleCancelledError
        if money.currency is not self.money.currency:
            raise TransactionCurrencyMismatchError
        return replace(self, money=money, description=description)

    def cancelled(self, at: datetime) -> RecurringRule:
        """Idempotente: cancelar dos veces conserva la primera fecha."""
        return self if self.is_cancelled else replace(self, cancelled_at=at)

    def _until(self, number: int, today: date) -> Iterator[Occurrence]:
        current = self.occurrence(number)
        while current.on <= today:
            yield current
            current = self.occurrence(current.number + 1)


@dataclass(frozen=True, slots=True)
class RuleDraft:
    kind: TransactionKind
    money: Money
    category: Category
    frequency: Frequency
    starts_on: date
    description: Description | None = None


def recurring_rule(
    draft: RuleDraft, account: TargetAccount, *, rule_id: UUID, owner_id: UUID, at: datetime
) -> RecurringRule:
    """Crea una regla válida o no la crea. Las reglas son las de un movimiento."""
    if account.is_archived:
        raise TransactionAccountArchivedError
    if draft.money.currency is not account.currency:
        raise TransactionCurrencyMismatchError
    if draft.category.kind is not draft.kind:
        raise CategoryKindMismatchError
    today = argentine_day(at)
    months = RecurringRule.START_RANGE_MONTHS
    if not add_months(today, -months) <= draft.starts_on <= add_months(today, months):
        raise RecurringStartOutOfRangeError
    return RecurringRule(
        id=rule_id,
        owner_id=owner_id,
        account_id=account.id,
        kind=draft.kind,
        category_id=draft.category.id,
        money=draft.money,
        frequency=draft.frequency,
        starts_on=draft.starts_on,
        created_at=at,
        description=draft.description,
    )
