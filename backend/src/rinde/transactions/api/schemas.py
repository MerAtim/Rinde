"""Esquemas de entrada y salida de movimientos.

Los montos viajan como string decimal (ADR-0002): un número en JSON pasa por el
`double` de JavaScript y 15300.50 deja de ser exacto.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer

from rinde.shared.domain.money import Currency
from rinde.transactions.application.ports import AccountBalance, Page
from rinde.transactions.application.use_cases import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.transaction import Description, Transaction


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
