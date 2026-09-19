"""Casos de uso de movimientos. Todos reciben el dueño: es el filtro de autorización."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from rinde.shared.domain.money import Money
from rinde.transactions.application.dependencies import TransactionsDependencies
from rinde.transactions.application.ports import (
    AccountBalance,
    IdempotentResource,
    Page,
    RememberedKey,
    TransactionFilters,
    TransferFilters,
    TransferPage,
)
from rinde.transactions.domain.category import Category, TransactionKind
from rinde.transactions.domain.errors import (
    CategoryNotFoundError,
    IdempotencyKeyReusedError,
    TransactionAccountArchivedError,
    TransactionAccountNotFoundError,
    TransactionNotFoundError,
    TransferNotFoundError,
)
from rinde.transactions.domain.transaction import (
    AuditAction,
    Description,
    Draft,
    TargetAccount,
    Transaction,
    register,
)
from rinde.transactions.domain.transfer import (
    Transfer,
    TransferDraft,
    TransferRoute,
    register_transfer,
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
                owner_id,
                idempotency_key,
                RememberedKey(data.fingerprint, IdempotentResource.TRANSACTION, transaction.id),
                now,
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
        if (
            remembered.fingerprint != data.fingerprint
            or remembered.resource is not IdempotentResource.TRANSACTION
        ):
            raise IdempotencyKeyReusedError
        return await self._deps.transactions.get(remembered.resource_id, owner_id)


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
    """Saldo por cuenta: sus movimientos vivos más lo que recibió menos lo que envió.

    Son dos consultas y una suma acá, que es el costo de que la transferencia sea
    una entidad propia (ADR-0014, decisión 1). Se junta en la aplicación y no en
    SQL para que cada repositorio siga siendo dueño de su tabla.
    """

    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID) -> list[AccountBalance]:
        totals: dict[UUID, Money] = {}
        for balance in await self._deps.transactions.balances_for_owner(owner_id):
            totals[balance.account_id] = balance.balance
        for balance in await self._deps.transfers.balances_for_owner(owner_id):
            # Las dos partes vienen en la moneda de la cuenta, que es una sola:
            # sumarlas no puede mezclar monedas.
            current = totals.get(balance.account_id)
            totals[balance.account_id] = (
                balance.balance if current is None else current + balance.balance
            )
        return [
            AccountBalance(account_id=account_id, balance=total)
            for account_id, total in totals.items()
        ]


@dataclass(frozen=True, slots=True)
class TransferInput:
    """Lo que llega del borde, ya con tipos, todavía sin reglas de dominio."""

    from_account_id: UUID
    to_account_id: UUID
    sent: Decimal
    received: Decimal
    occurred_on: date
    description: str | None = None

    @property
    def fingerprint(self) -> str:
        """Huella del pedido, para distinguir un reintento de una clave reusada."""
        raw = _SEPARATOR.join(
            [
                str(self.from_account_id),
                str(self.to_account_id),
                str(self.sent),
                str(self.received),
                self.occurred_on.isoformat(),
                self.description or "",
            ]
        )
        return sha256(raw.encode()).hexdigest()


async def _owned_transfer(
    deps: TransactionsDependencies, transfer_id: UUID, owner_id: UUID
) -> Transfer:
    transfer = await deps.transfers.get(transfer_id, owner_id)
    if transfer is None:
        raise TransferNotFoundError
    return transfer


async def _route(
    deps: TransactionsDependencies, data: TransferInput, owner_id: UUID
) -> TransferRoute:
    """Las dos cuentas, de la persona y activas. Hacia la misma cuenta no se construye."""
    origin = await _account(deps, data.from_account_id, owner_id)
    destination = await _account(deps, data.to_account_id, owner_id)
    return TransferRoute(origin, destination)


def _transfer_draft(data: TransferInput, route: TransferRoute) -> TransferDraft:
    return TransferDraft(
        # Cada lado en la moneda de su cuenta: Money valida la precisión de cada una.
        sent=Money(data.sent, route.origin.currency),
        received=Money(data.received, route.destination.currency),
        occurred_on=data.occurred_on,
        description=Description.parse(data.description),
    )


class RegisterTransfer:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(
        self, owner_id: UUID, data: TransferInput, idempotency_key: str | None = None
    ) -> Transfer:
        deps = self._deps
        if idempotency_key is not None:
            repeated = await self._repeated(owner_id, data, idempotency_key)
            if repeated is not None:
                return repeated

        route = await _route(deps, data, owner_id)
        draft = _transfer_draft(data, route)
        now = deps.clock.now()
        transfer = register_transfer(draft, route, transfer_id=uuid4(), owner_id=owner_id, at=now)
        await deps.transfers.add(transfer)
        await deps.transfer_audit.record(AuditAction.REGISTERED, transfer, now)
        if idempotency_key is not None:
            await deps.idempotency.remember(
                owner_id,
                idempotency_key,
                RememberedKey(data.fingerprint, IdempotentResource.TRANSFER, transfer.id),
                now,
            )
            await deps.idempotency.forget_expired(now - IDEMPOTENCY_TTL)
        await deps.transaction.commit()
        return transfer

    async def _repeated(self, owner_id: UUID, data: TransferInput, key: str) -> Transfer | None:
        """La transferencia que ya creó esta clave, si el pedido es el mismo."""
        remembered = await self._deps.idempotency.recall(owner_id, key)
        if remembered is None:
            return None
        if (
            remembered.fingerprint != data.fingerprint
            or remembered.resource is not IdempotentResource.TRANSFER
        ):
            raise IdempotencyKeyReusedError
        return await self._deps.transfers.get(remembered.resource_id, owner_id)


class EditTransfer:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, transfer_id: UUID, data: TransferInput) -> Transfer:
        deps = self._deps
        transfer = await _owned_transfer(deps, transfer_id, owner_id)
        # Acá sí se pueden cambiar las cuentas: elegir mal el origen o el destino
        # es el error más fácil de cometer al cargar una transferencia.
        route = await _route(deps, data, owner_id)
        draft = _transfer_draft(data, route)
        now = deps.clock.now()
        edited = transfer.edited(draft, route, at=now)
        await deps.transfers.save(edited)
        await deps.transfer_audit.record(AuditAction.EDITED, edited, now)
        await deps.transaction.commit()
        return edited


class DeleteTransfer:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, transfer_id: UUID) -> Transfer:
        deps = self._deps
        transfer = await _owned_transfer(deps, transfer_id, owner_id)
        now = deps.clock.now()
        deleted = transfer.deleted(now)
        if deleted is not transfer:
            await deps.transfers.save(deleted)
            await deps.transfer_audit.record(AuditAction.DELETED, deleted, now)
            await deps.transaction.commit()
        return deleted


class RestoreTransfer:
    """Deshacer un borrado, que es lo que ofrece la interfaz en lugar de preguntar."""

    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, transfer_id: UUID) -> Transfer:
        deps = self._deps
        transfer = await _owned_transfer(deps, transfer_id, owner_id)
        now = deps.clock.now()
        restored = transfer.restored(now)
        if restored is not transfer:
            await deps.transfers.save(restored)
            await deps.transfer_audit.record(AuditAction.RESTORED, restored, now)
            await deps.transaction.commit()
        return restored


class GetTransfer:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, transfer_id: UUID) -> Transfer:
        transfer = await _owned_transfer(self._deps, transfer_id, owner_id)
        if transfer.is_deleted:
            # Para quien consulta, una transferencia borrada ya no está.
            raise TransferNotFoundError
        return transfer


class ListTransfers:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(
        self,
        owner_id: UUID,
        filters: TransferFilters,
        *,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> TransferPage:
        size = min(max(limit, 1), MAX_PAGE_SIZE)
        return await self._deps.transfers.page_for_owner(
            owner_id, filters, cursor=cursor, limit=size
        )
