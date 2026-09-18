"""Casos de uso de movimientos. Todos reciben el dueño: es el filtro de autorización."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from rinde.shared.domain.money import Money
from rinde.transactions.application.dependencies import TransactionsDependencies
from rinde.transactions.application.ports import AccountBalance, Page, TransactionFilters
from rinde.transactions.domain.category import Category, TransactionKind
from rinde.transactions.domain.errors import (
    CategoryNotFoundError,
    IdempotencyKeyReusedError,
    TransactionAccountArchivedError,
    TransactionAccountNotFoundError,
    TransactionNotFoundError,
)
from rinde.transactions.domain.transaction import (
    AuditAction,
    Description,
    Draft,
    TargetAccount,
    Transaction,
    register,
)

# Una clave de idempotencia sirve para reintentar un pedido que quedó en el aire,
# no para siempre: pasado un día, se olvida.
IDEMPOTENCY_TTL = timedelta(days=1)
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class TransactionInput:
    """Lo que llega del borde, ya con tipos, todavía sin reglas de dominio."""

    account_id: UUID
    kind: TransactionKind
    amount: Decimal
    category_id: UUID
    occurred_on: date
    description: str | None = None

    @property
    def fingerprint(self) -> str:
        """Huella del pedido, para distinguir un reintento de una clave reusada."""
        raw = _SEPARATOR.join(
            [
                str(self.account_id),
                self.kind.value,
                str(self.amount),
                str(self.category_id),
                self.occurred_on.isoformat(),
                self.description or "",
            ]
        )
        return sha256(raw.encode()).hexdigest()


_SEPARATOR = "\x1f"


async def _owned(
    deps: TransactionsDependencies, transaction_id: UUID, owner_id: UUID
) -> Transaction:
    transaction = await deps.transactions.get(transaction_id, owner_id)
    if transaction is None:
        raise TransactionNotFoundError
    return transaction


async def _account(
    deps: TransactionsDependencies, account_id: UUID, owner_id: UUID
) -> TargetAccount:
    account = await deps.accounts.target(account_id, owner_id)
    if account is None:
        raise TransactionAccountNotFoundError
    if account.is_archived:
        raise TransactionAccountArchivedError
    return account


async def _category(deps: TransactionsDependencies, category_id: UUID, owner_id: UUID) -> Category:
    category = await deps.categories.get(category_id, owner_id)
    if category is None:
        raise CategoryNotFoundError
    return category


async def _draft(
    deps: TransactionsDependencies, data: TransactionInput, owner_id: UUID, account: TargetAccount
) -> Draft:
    return Draft(
        kind=data.kind,
        # Money valida la precisión de la moneda: 10,999 pesos no se redondea solo.
        money=Money(data.amount, account.currency),
        category=await _category(deps, data.category_id, owner_id),
        occurred_on=data.occurred_on,
        description=Description.parse(data.description),
    )


class RegisterTransaction:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(
        self, owner_id: UUID, data: TransactionInput, idempotency_key: str | None = None
    ) -> Transaction:
        deps = self._deps
        if idempotency_key is not None:
            repeated = await self._repeated(owner_id, data, idempotency_key)
            if repeated is not None:
                return repeated

        account = await _account(deps, data.account_id, owner_id)
        draft = await _draft(deps, data, owner_id, account)
        now = deps.clock.now()
        transaction = register(draft, account, transaction_id=uuid4(), owner_id=owner_id, at=now)
        await deps.transactions.add(transaction)
        await deps.audit.record(AuditAction.REGISTERED, transaction, now)
        if idempotency_key is not None:
            await deps.idempotency.remember(
                owner_id, idempotency_key, data.fingerprint, transaction.id, now
            )
            await deps.idempotency.forget_expired(now - IDEMPOTENCY_TTL)
        await deps.transaction.commit()
        return transaction

    async def _repeated(
        self, owner_id: UUID, data: TransactionInput, key: str
    ) -> Transaction | None:
        """El movimiento que ya creó esta clave, si el pedido es el mismo."""
        remembered = await self._deps.idempotency.recall(owner_id, key)
        if remembered is None:
            return None
        fingerprint, transaction_id = remembered
        if fingerprint != data.fingerprint:
            raise IdempotencyKeyReusedError
        return await self._deps.transactions.get(transaction_id, owner_id)


class EditTransaction:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(
        self, owner_id: UUID, transaction_id: UUID, data: TransactionInput
    ) -> Transaction:
        deps = self._deps
        transaction = await _owned(deps, transaction_id, owner_id)
        # La cuenta no se cambia al editar: mover plata de cuenta es otra operación.
        account = await _account(deps, transaction.account_id, owner_id)
        draft = await _draft(deps, data, owner_id, account)
        now = deps.clock.now()
        edited = transaction.edited(draft, now)
        await deps.transactions.save(edited)
        await deps.audit.record(AuditAction.EDITED, edited, now)
        await deps.transaction.commit()
        return edited


class DeleteTransaction:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, transaction_id: UUID) -> Transaction:
        deps = self._deps
        transaction = await _owned(deps, transaction_id, owner_id)
        now = deps.clock.now()
        deleted = transaction.deleted(now)
        if deleted is not transaction:
            await deps.transactions.save(deleted)
            await deps.audit.record(AuditAction.DELETED, deleted, now)
            await deps.transaction.commit()
        return deleted


class RestoreTransaction:
    """Deshacer un borrado, que es lo que ofrece la interfaz en lugar de preguntar."""

    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, transaction_id: UUID) -> Transaction:
        deps = self._deps
        transaction = await _owned(deps, transaction_id, owner_id)
        now = deps.clock.now()
        restored = transaction.restored(now)
        if restored is not transaction:
            await deps.transactions.save(restored)
            await deps.audit.record(AuditAction.RESTORED, restored, now)
            await deps.transaction.commit()
        return restored


class GetTransaction:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, transaction_id: UUID) -> Transaction:
        transaction = await _owned(self._deps, transaction_id, owner_id)
        if transaction.is_deleted:
            # Para quien consulta, un movimiento borrado ya no está.
            raise TransactionNotFoundError
        return transaction


class ListTransactions:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(
        self,
        owner_id: UUID,
        filters: TransactionFilters,
        *,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Page:
        size = min(max(limit, 1), MAX_PAGE_SIZE)
        return await self._deps.transactions.page_for_owner(
            owner_id, filters, cursor=cursor, limit=size
        )


class ListBalances:
    """Saldo por cuenta: la suma de sus movimientos vivos (ADR-0009, ADR-0011)."""

    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID) -> list[AccountBalance]:
        return await self._deps.transactions.balances_for_owner(owner_id)
