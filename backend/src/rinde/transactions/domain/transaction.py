"""El movimiento: cuánta plata entró o salió, de qué cuenta y cuándo (ADR-0011)."""

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import ClassVar
from uuid import UUID

from rinde.shared.domain.money import Currency, Money
from rinde.shared.domain.text import is_clean, normalize
from rinde.transactions.domain.category import Category, TransactionKind
from rinde.transactions.domain.errors import (
    CategoryKindMismatchError,
    TransactionAmountNotPositiveError,
    TransactionCurrencyMismatchError,
    TransactionDateInFutureError,
    TransactionDeletedError,
    TransactionDescriptionInvalidError,
)

# La fecha la elige la persona y su reloj puede ir adelantado del UTC del servidor.
# Un día de tolerancia evita rechazar un gasto de esta noche en Buenos Aires.
_FUTURE_TOLERANCE = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class Description:
    """Texto libre y opcional: "asado con los del trabajo"."""

    MAX_LENGTH: ClassVar[int] = 120
    value: str

    @classmethod
    def parse(cls, raw: str | None) -> Description | None:
        if raw is None:
            return None
        value = normalize(raw)
        if not value:
            return None
        if len(value) > cls.MAX_LENGTH or not is_clean(value):
            raise TransactionDescriptionInvalidError
        return cls(value)


@dataclass(frozen=True, slots=True)
class TargetAccount:
    """Lo único que movimientos necesita saber de una cuenta: cuál es y en qué moneda."""

    id: UUID
    currency: Currency


@dataclass(frozen=True, slots=True)
class Draft:
    """Lo que la persona carga. Registrar y editar validan lo mismo, acá."""

    kind: TransactionKind
    money: Money
    category: Category
    occurred_on: date
    description: Description | None = None

    def check(self, currency: Currency, at: datetime) -> None:
        if not self.money.is_positive:
            raise TransactionAmountNotPositiveError
        if self.money.currency is not currency:
            raise TransactionCurrencyMismatchError
        if self.category.kind is not self.kind:
            raise CategoryKindMismatchError
        if self.occurred_on > (at + _FUTURE_TOLERANCE).date():
            raise TransactionDateInFutureError


@dataclass(frozen=True, slots=True)
class Transaction:
    id: UUID
    owner_id: UUID
    account_id: UUID
    kind: TransactionKind
    money: Money
    """Siempre positivo: el signo lo da `kind` (ADR-0011)."""
    category_id: UUID
    occurred_on: date
    """Fecha de valor: cuándo pasó, que no siempre es cuándo se anotó."""
    created_at: datetime
    updated_at: datetime
    description: Description | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        # En todo movimiento, no solo al registrarlo: también en el que se lee de la base.
        if not self.money.is_positive:
            raise TransactionAmountNotPositiveError

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def signed_amount(self) -> Money:
        """Lo que le suma a la cuenta: negativo si es un gasto."""
        return self.money if self.kind is TransactionKind.INCOME else -self.money

    def edited(self, draft: Draft, at: datetime) -> Transaction:
        """Edita todo junto: las reglas cruzan los campos y se validan de una."""
        if self.is_deleted:
            raise TransactionDeletedError
        draft.check(self.money.currency, at)
        return replace(
            self,
            kind=draft.kind,
            money=draft.money,
            category_id=draft.category.id,
            occurred_on=draft.occurred_on,
            description=draft.description,
            updated_at=at,
        )

    def deleted(self, at: datetime) -> Transaction:
        """Idempotente: borrar dos veces conserva la primera fecha (ADR-0011)."""
        return self if self.is_deleted else replace(self, deleted_at=at, updated_at=at)

    def restored(self, at: datetime) -> Transaction:
        """Deshacer un borrado, mientras la persona sigue mirando la pantalla."""
        return self if not self.is_deleted else replace(self, deleted_at=None, updated_at=at)


def register(
    draft: Draft, account: TargetAccount, *, transaction_id: UUID, owner_id: UUID, at: datetime
) -> Transaction:
    """Crea un movimiento válido o no lo crea."""
    draft.check(account.currency, at)
    return Transaction(
        id=transaction_id,
        owner_id=owner_id,
        account_id=account.id,
        kind=draft.kind,
        money=draft.money,
        category_id=draft.category.id,
        occurred_on=draft.occurred_on,
        created_at=at,
        updated_at=at,
        description=draft.description,
    )
