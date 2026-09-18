"""Repositorios de movimientos sobre PostgreSQL. No confirman: lo hace la transacción.

Ninguna lectura arma su propia consulta: todas parten de `_alive`, que ya excluye
los movimientos borrados. Es la mitigación del borrado lógico (ADR-0011).
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, Select, case, delete, func, insert, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from rinde.shared.domain.money import Currency, Money
from rinde.transactions.application.pagination import Cursor
from rinde.transactions.application.ports import AccountBalance, Page, TransactionFilters
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.transaction import (
    AuditAction,
    Description,
    Transaction,
)
from rinde.transactions.infrastructure.tables import (
    categories,
    idempotency_keys,
    transaction_audit,
    transactions,
)


def _to_transaction(row: RowMapping) -> Transaction:
    currency = Currency(row["currency"])
    return Transaction(
        id=row["id"],
        owner_id=row["owner_id"],
        account_id=row["account_id"],
        kind=TransactionKind(row["kind"]),
        # El monto viene con la escala de la columna; se ajusta a la de su moneda.
        money=Money(Decimal(row["amount"]).quantize(currency.quantum), currency),
        category_id=row["category_id"],
        occurred_on=row["occurred_on"],
        description=Description(row["description"]) if row["description"] else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
    )


def _values(transaction: Transaction) -> dict[str, object]:
    return {
        "id": transaction.id,
        "owner_id": transaction.owner_id,
        "account_id": transaction.account_id,
        "currency": transaction.money.currency.value,
        "kind": transaction.kind.value,
        "amount": transaction.money.amount,
        "category_id": transaction.category_id,
        "occurred_on": transaction.occurred_on,
        "description": transaction.description.value if transaction.description else None,
        "created_at": transaction.created_at,
        "updated_at": transaction.updated_at,
        "deleted_at": transaction.deleted_at,
    }


class SqlAlchemyTransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _alive(self, owner_id: UUID) -> Select[tuple[object, ...]]:
        """El único punto de entrada de las lecturas: sin borrados y con dueño."""
        return select(transactions).where(
            transactions.c.owner_id == owner_id, transactions.c.deleted_at.is_(None)
        )

    async def add(self, transaction: Transaction) -> None:
        await self._session.execute(insert(transactions).values(**_values(transaction)))

    async def get(self, transaction_id: UUID, owner_id: UUID) -> Transaction | None:
        # La única lectura que incluye borrados: hace falta para deshacer.
        result = await self._session.execute(
            select(transactions).where(
                transactions.c.id == transaction_id, transactions.c.owner_id == owner_id
            )
        )
        row = result.mappings().one_or_none()
        return _to_transaction(row) if row else None

    async def page_for_owner(
        self, owner_id: UUID, filters: TransactionFilters, *, cursor: str | None, limit: int
    ) -> Page:
        query = self._alive(owner_id)
        if filters.account_id is not None:
            query = query.where(transactions.c.account_id == filters.account_id)
        if filters.since is not None:
            query = query.where(transactions.c.occurred_on >= filters.since)
        if filters.until is not None:
            query = query.where(transactions.c.occurred_on <= filters.until)
        if cursor is not None:
            mark = Cursor.decode(cursor)
            # Menor que el par (fecha, id): continúa justo después de la última fila.
            query = query.where(
                tuple_(transactions.c.occurred_on, transactions.c.id)
                < (mark.occurred_on, mark.transaction_id)
            )
        query = query.order_by(transactions.c.occurred_on.desc(), transactions.c.id.desc())
        # Una fila de más para saber si hay página siguiente, sin contar el total.
        result = await self._session.execute(query.limit(limit + 1))
        rows = [_to_transaction(row) for row in result.mappings()]
        if len(rows) > limit:
            last = rows[limit - 1]
            return Page(items=rows[:limit], next_cursor=Cursor(last.occurred_on, last.id).encode())
        return Page(items=rows, next_cursor=None)

    async def balances_for_owner(self, owner_id: UUID) -> list[AccountBalance]:
        # El signo lo da el tipo (ADR-0011): los ingresos suman y los gastos restan.
        signed = func.sum(
            case(
                (transactions.c.kind == TransactionKind.INCOME.value, transactions.c.amount),
                else_=-transactions.c.amount,
            )
        )
        query = (
            self._alive(owner_id)
            .with_only_columns(transactions.c.account_id, transactions.c.currency, signed)
            .group_by(transactions.c.account_id, transactions.c.currency)
        )
        result = await self._session.execute(query)
        balances = []
        for account_id, currency_code, total in result.all():
            currency = Currency(currency_code)
            balances.append(
                AccountBalance(
                    account_id=account_id,
                    balance=Money(Decimal(total).quantize(currency.quantum), currency),
                )
            )
        return balances

    async def count_by_category(self, category_id: UUID, owner_id: UUID) -> int:
        query = self._alive(owner_id).where(transactions.c.category_id == category_id)
        result = await self._session.execute(select(func.count()).select_from(query.subquery()))
        return int(result.scalar_one())

    async def save(self, transaction: Transaction) -> None:
        values = _values(transaction)
        del values["id"], values["owner_id"], values["created_at"]
        await self._session.execute(
            update(transactions)
            .where(
                transactions.c.id == transaction.id,
                transactions.c.owner_id == transaction.owner_id,
            )
            .values(**values)
        )


def _to_category(row: RowMapping) -> Category:
    return Category(
        id=row["id"],
        owner_id=row["owner_id"],
        name=CategoryName(row["name"]),
        kind=TransactionKind(row["kind"]),
        created_at=row["created_at"],
        slug=row["slug"],
    )


class SqlAlchemyCategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, category: Category) -> None:
        await self._session.execute(insert(categories).values(**self._values(category)))

    async def add_seeds(self, seeds: list[Category]) -> None:
        # Si otra siembra simultánea ganó, esta no escribe nada y no falla.
        await self._session.execute(
            pg_insert(categories)
            .values([self._values(seed) for seed in seeds])
            .on_conflict_do_nothing()
        )

    async def get(self, category_id: UUID, owner_id: UUID) -> Category | None:
        result = await self._session.execute(
            select(categories).where(
                categories.c.id == category_id, categories.c.owner_id == owner_id
            )
        )
        row = result.mappings().one_or_none()
        return _to_category(row) if row else None

    async def list_for_owner(self, owner_id: UUID) -> list[Category]:
        result = await self._session.execute(
            select(categories)
            .where(categories.c.owner_id == owner_id)
            .order_by(categories.c.kind, func.lower(categories.c.name))
        )
        return [_to_category(row) for row in result.mappings()]

    async def find_by_name(
        self, owner_id: UUID, comparable: str, kind: TransactionKind
    ) -> Category | None:
        result = await self._session.execute(
            select(categories).where(
                categories.c.owner_id == owner_id,
                categories.c.kind == kind.value,
                func.lower(categories.c.name) == comparable,
            )
        )
        row = result.mappings().one_or_none()
        return _to_category(row) if row else None

    async def save(self, category: Category) -> None:
        await self._session.execute(
            update(categories)
            .where(categories.c.id == category.id, categories.c.owner_id == category.owner_id)
            .values(name=category.name.value, slug=category.slug)
        )

    async def delete(self, category_id: UUID, owner_id: UUID) -> None:
        await self._session.execute(
            delete(categories).where(
                categories.c.id == category_id, categories.c.owner_id == owner_id
            )
        )

    @staticmethod
    def _values(category: Category) -> dict[str, object]:
        return {
            "id": category.id,
            "owner_id": category.owner_id,
            "name": category.name.value,
            "kind": category.kind.value,
            "slug": category.slug,
            "created_at": category.created_at,
        }


class SqlAlchemyAuditLog:
    """Solo inserta. La base rechaza cualquier otra cosa (ADR-0011)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, action: AuditAction, transaction: Transaction, at: datetime) -> None:
        await self._session.execute(
            insert(transaction_audit).values(
                id=uuid4(),
                transaction_id=transaction.id,
                owner_id=transaction.owner_id,
                action=action.value,
                recorded_at=at,
                snapshot={
                    "account_id": str(transaction.account_id),
                    "kind": transaction.kind.value,
                    "amount": str(transaction.money.amount),
                    "currency": transaction.money.currency.value,
                    "category_id": str(transaction.category_id),
                    "occurred_on": transaction.occurred_on.isoformat(),
                    "description": transaction.description.value
                    if transaction.description
                    else None,
                    "deleted_at": transaction.deleted_at.isoformat()
                    if transaction.deleted_at
                    else None,
                },
            )
        )


class SqlAlchemyIdempotencyStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def remember(
        self, owner_id: UUID, key: str, fingerprint: str, transaction_id: UUID, at: datetime
    ) -> None:
        await self._session.execute(
            insert(idempotency_keys).values(
                owner_id=owner_id,
                key=key,
                fingerprint=fingerprint,
                transaction_id=transaction_id,
                created_at=at,
            )
        )

    async def recall(self, owner_id: UUID, key: str) -> tuple[str, UUID] | None:
        result = await self._session.execute(
            select(idempotency_keys.c.fingerprint, idempotency_keys.c.transaction_id).where(
                idempotency_keys.c.owner_id == owner_id, idempotency_keys.c.key == key
            )
        )
        row = result.one_or_none()
        return (row[0], row[1]) if row else None

    async def forget_expired(self, before: datetime) -> None:
        await self._session.execute(
            delete(idempotency_keys).where(idempotency_keys.c.created_at < before)
        )
