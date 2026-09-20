"""Esquemas de entrada y salida de movimientos.

Los montos viajan como string decimal (ADR-0002): un número en JSON pasa por el
`double` de JavaScript y 15300.50 deja de ser exacto.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer

from rinde.shared.domain.money import Currency
from rinde.transactions.application.ports import (
    AccountBalance,
    HistoryPage,
    Page,
    TransferPage,
)
from rinde.transactions.application.use_cases import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.transaction import Description, Transaction
from rinde.transactions.domain.transfer import Transfer


def _decimal_from_string(value: object) -> Decimal:
    """Solo string: un número en JSON pasa por el `double` y ya perdió precisión."""
    if not isinstance(value, str):
        raise ValueError("el monto viaja como string decimal, no como número")
    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError("no es un monto decimal") from None


AmountIn = Annotated[
    Decimal,
    BeforeValidator(_decimal_from_string, json_schema_input_type=str),
    PlainSerializer(str, return_type=str),
    Field(description='Monto positivo como string decimal, por ejemplo "15300.50"'),
]
AmountOut = Annotated[Decimal, PlainSerializer(str, return_type=str)]


class TransactionQuery(BaseModel):
    """Filtros y paginación de la lista, como parámetros de consulta."""

    model_config = ConfigDict(extra="forbid")

    account_id: UUID | None = None
    since: date | None = None
    until: date | None = None
    category_id: UUID | None = None
    q: str | None = Field(
        default=None,
        max_length=Description.MAX_LENGTH,
        description="Busca en la descripción, sin distinguir tildes ni mayúsculas",
    )
    cursor: str | None = None
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class RegisterTransactionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: UUID
    kind: TransactionKind
    amount: AmountIn
    category_id: UUID
    occurred_on: date
    description: str | None = Field(default=None, max_length=Description.MAX_LENGTH)


class EditTransactionRequest(BaseModel):
    """La cuenta no se edita: mover plata de cuenta es otra operación."""

    model_config = ConfigDict(extra="forbid")

    kind: TransactionKind
    amount: AmountIn
    category_id: UUID
    occurred_on: date
    description: str | None = Field(default=None, max_length=Description.MAX_LENGTH)


class TransactionResponse(BaseModel):
    id: UUID
    account_id: UUID
    kind: TransactionKind
    amount: AmountOut
    currency: Currency
    category_id: UUID
    occurred_on: date
    description: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_transaction(cls, transaction: Transaction) -> TransactionResponse:
        return cls(
            id=transaction.id,
            account_id=transaction.account_id,
            kind=transaction.kind,
            amount=transaction.money.amount,
            currency=transaction.money.currency,
            category_id=transaction.category_id,
            occurred_on=transaction.occurred_on,
            description=transaction.description.value if transaction.description else None,
            created_at=transaction.created_at,
            updated_at=transaction.updated_at,
            deleted_at=transaction.deleted_at,
        )


class TransactionPageResponse(BaseModel):
    items: list[TransactionResponse]
    next_cursor: str | None
    """Se pasa tal cual en `cursor` para pedir la página siguiente."""

    @classmethod
    def from_page(cls, page: Page) -> TransactionPageResponse:
        return cls(
            items=[TransactionResponse.from_transaction(row) for row in page.items],
            next_cursor=page.next_cursor,
        )


class BalanceResponse(BaseModel):
    account_id: UUID
    amount: AmountOut
    currency: Currency

    @classmethod
    def from_balance(cls, balance: AccountBalance) -> BalanceResponse:
        return cls(
            account_id=balance.account_id,
            amount=balance.balance.amount,
            currency=balance.balance.currency,
        )


class TransferQuery(BaseModel):
    """Filtros y paginación de la lista, como parámetros de consulta."""

    model_config = ConfigDict(extra="forbid")

    account_id: UUID | None = None
    """Alcanza a la cuenta esté de un lado o del otro de la transferencia."""
    since: date | None = None
    until: date | None = None
    cursor: str | None = None
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class TransferRequest(BaseModel):
    """Registrar y editar piden lo mismo: las cuentas también se pueden corregir.

    Los dos montos viajan siempre, incluso entre cuentas de la misma moneda: una
    transferencia con comisión saca 1000 y deposita 990 (ADR-0014, decisión 2).
    """

    model_config = ConfigDict(extra="forbid")

    from_account_id: UUID
    to_account_id: UUID
    sent: AmountIn = Field(description="Lo que sale, en la moneda de la cuenta de origen")
    received: AmountIn = Field(description="Lo que entra, en la moneda de la de destino")
    occurred_on: date
    description: str | None = Field(default=None, max_length=Description.MAX_LENGTH)


class TransferResponse(BaseModel):
    id: UUID
    from_account_id: UUID
    sent: AmountOut
    currency_out: Currency
    to_account_id: UUID
    received: AmountOut
    currency_in: Currency
    occurred_on: date
    description: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_transfer(cls, transfer: Transfer) -> TransferResponse:
        return cls(
            id=transfer.id,
            from_account_id=transfer.from_account_id,
            sent=transfer.sent.amount,
            currency_out=transfer.sent.currency,
            to_account_id=transfer.to_account_id,
            received=transfer.received.amount,
            currency_in=transfer.received.currency,
            occurred_on=transfer.occurred_on,
            description=transfer.description.value if transfer.description else None,
            created_at=transfer.created_at,
            updated_at=transfer.updated_at,
            deleted_at=transfer.deleted_at,
        )


class TransferPageResponse(BaseModel):
    items: list[TransferResponse]
    next_cursor: str | None
    """Se pasa tal cual en `cursor` para pedir la página siguiente."""

    @classmethod
    def from_page(cls, page: TransferPage) -> TransferPageResponse:
        return cls(
            items=[TransferResponse.from_transfer(row) for row in page.items],
            next_cursor=page.next_cursor,
        )


class HistoryTransaction(BaseModel):
    """Un movimiento dentro del historial."""

    type: Literal["transaction"] = "transaction"
    transaction: TransactionResponse


class HistoryTransfer(BaseModel):
    """Una transferencia dentro del historial."""

    type: Literal["transfer"] = "transfer"
    transfer: TransferResponse


# Unión discriminada: quien la consume sabe cuál de las dos es sin adivinar.
HistoryEntry = Annotated[HistoryTransaction | HistoryTransfer, Field(discriminator="type")]


class HistoryPageResponse(BaseModel):
    """Movimientos y transferencias en una sola línea de tiempo (ADR-0014)."""

    items: list[HistoryEntry]
    next_cursor: str | None
    """Se pasa tal cual en `cursor` para pedir la página siguiente."""

    @classmethod
    def from_page(cls, page: HistoryPage) -> HistoryPageResponse:
        return cls(
            items=[
                HistoryTransfer(transfer=TransferResponse.from_transfer(item))
                if isinstance(item, Transfer)
                else HistoryTransaction(transaction=TransactionResponse.from_transaction(item))
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )


class CategoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=CategoryName.MAX_LENGTH)
    kind: TransactionKind


class RenameCategoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=CategoryName.MAX_LENGTH)


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    kind: TransactionKind
    slug: str | None
    """Solo en las sembradas: la interfaz las traduce por este identificador."""

    @classmethod
    def from_category(cls, category: Category) -> CategoryResponse:
        return cls(id=category.id, name=category.name.value, kind=category.kind, slug=category.slug)
