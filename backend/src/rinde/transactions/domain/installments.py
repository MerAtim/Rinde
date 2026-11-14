"""Compras en cuotas: un plan que se vuelve movimientos de a uno (ADR-0026).

Cada cuota cuenta en su mes. Una cuota se vuelve movimiento recién cuando llega
su fecha: así ningún movimiento tiene fecha futura, y todo lo que lee
movimientos (saldos, presupuestos, dashboard) sigue viendo solo lo que pasó.
"""

from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import ClassVar
from uuid import UUID

from rinde.shared.domain.allocation import split_equally
from rinde.shared.domain.money import Money
from rinde.transactions.domain.category import Category, TransactionKind
from rinde.transactions.domain.errors import (
    CategoryKindMismatchError,
    InstallmentAmountTooSmallError,
    InstallmentCountInvalidError,
    TransactionAccountArchivedError,
    TransactionAmountNotPositiveError,
    TransactionCurrencyMismatchError,
    TransactionDateInFutureError,
)
from rinde.transactions.domain.transaction import (
    FUTURE_TOLERANCE,
    Description,
    Draft,
    TargetAccount,
)


def due_on(first: date, number: int) -> date:
    """La cuota `number` (desde 1): el mismo día, `number - 1` meses después.

    Un 31 en un mes de 30 días cae el último día del mes.
    """
    index = first.year * 12 + first.month - 1 + number - 1
    year, month = index // 12, index % 12 + 1
    return date(year, month, min(first.day, monthrange(year, month)[1]))


@dataclass(frozen=True, slots=True)
class Installment:
    number: int
    due_on: date
    money: Money


@dataclass(frozen=True, slots=True)
class InstallmentPlan:
    MIN_COUNT: ClassVar[int] = 2
    MAX_COUNT: ClassVar[int] = 48

    id: UUID
    owner_id: UUID
    account_id: UUID
    category_id: UUID
    total: Money
    """Lo que se paga en total, con interés o sin él: Rinde no calcula intereses."""
    count: int
    first_on: date
    """El día de la compra, que es el de la primera cuota."""
    created_at: datetime
    description: Description | None = None
    cancelled_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.MIN_COUNT <= self.count <= self.MAX_COUNT:
            raise InstallmentCountInvalidError
        if not self.total.is_positive:
            raise TransactionAmountNotPositiveError
        if self.total.amount < self.total.currency.quantum * self.count:
            raise InstallmentAmountTooSmallError

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled_at is not None

    def schedule(self) -> list[Installment]:
        """Todas las cuotas. Suman exactamente el total (ADR-0026)."""
        return [
            Installment(number, due_on(self.first_on, number), money)
            for number, money in enumerate(split_equally(self.total, self.count), start=1)
        ]

    def due(self, today: date) -> list[Installment]:
        """Las que ya llegaron. Un plan cancelado no genera más."""
        if self.is_cancelled:
            return []
        return [item for item in self.schedule() if item.due_on <= today]

    def draft(self, installment: Installment, category: Category) -> Draft:
        """El movimiento de una cuota: un gasto común, con la descripción del plan."""
        return Draft(
            kind=TransactionKind.EXPENSE,
            money=installment.money,
            category=category,
            occurred_on=installment.due_on,
            description=self.description,
        )

    def cancelled(self, at: datetime) -> InstallmentPlan:
        """Idempotente: cancelar dos veces conserva la primera fecha."""
        return self if self.is_cancelled else replace(self, cancelled_at=at)


@dataclass(frozen=True, slots=True)
class PlanDraft:
    total: Money
    count: int
    category: Category
    first_on: date
    description: Description | None = None


def plan(
    draft: PlanDraft, account: TargetAccount, *, plan_id: UUID, owner_id: UUID, at: datetime
) -> InstallmentPlan:
    """Crea un plan válido o no lo crea. Las reglas son las de un gasto."""
    if account.is_archived:
        raise TransactionAccountArchivedError
    if draft.total.currency is not account.currency:
        raise TransactionCurrencyMismatchError
    if draft.category.kind is not TransactionKind.EXPENSE:
        raise CategoryKindMismatchError
    if draft.first_on > (at + FUTURE_TOLERANCE).date():
        raise TransactionDateInFutureError
    return InstallmentPlan(
        id=plan_id,
        owner_id=owner_id,
        account_id=account.id,
        category_id=draft.category.id,
        total=draft.total,
        count=draft.count,
        first_on=draft.first_on,
        created_at=at,
        description=draft.description,
    )
