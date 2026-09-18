"""Puertos del módulo de movimientos.

Como en cuentas, ninguna lectura acepta solo un identificador: siempre pide
también el dueño, así un caso de uso no puede olvidarse de filtrar por el
usuario autenticado. Y ningún listado devuelve movimientos borrados (ADR-0011).
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from rinde.shared.domain.money import Money
from rinde.transactions.domain.category import Category, TransactionKind
from rinde.transactions.domain.transaction import AuditAction, TargetAccount, Transaction


@dataclass(frozen=True, slots=True)
class TransactionFilters:
    """Lo que la lista puede acotar. Todo opcional: sin nada, son todos."""

    account_id: UUID | None = None
    since: date | None = None
    until: date | None = None


@dataclass(frozen=True, slots=True)
class Page:
    """Una porción de la lista, con la marca para pedir la siguiente."""

    items: list[Transaction]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class AccountBalance:
    account_id: UUID
    balance: Money


class TransactionRepository(Protocol):
    async def add(self, transaction: Transaction) -> None: ...

    async def get(self, transaction_id: UUID, owner_id: UUID) -> Transaction | None:
        """Devuelve también el borrado: hace falta para deshacer."""
        ...

    async def page_for_owner(
        self, owner_id: UUID, filters: TransactionFilters, *, cursor: str | None, limit: int
    ) -> Page:
        """De la más reciente a la más vieja, sin los borrados."""
        ...

    async def balances_for_owner(self, owner_id: UUID) -> list[AccountBalance]:
        """Saldo por cuenta, sin los borrados. Cada saldo en la moneda de su cuenta."""
        ...

    async def count_by_category(self, category_id: UUID, owner_id: UUID) -> int: ...

    async def save(self, transaction: Transaction) -> None: ...


class CategoryRepository(Protocol):
    async def add(self, category: Category) -> None: ...

    async def add_seeds(self, categories: list[Category]) -> None:
        """Siembra la primera vez. Si otra siembra simultánea ganó, no escribe nada."""
        ...

    async def get(self, category_id: UUID, owner_id: UUID) -> Category | None: ...

    async def list_for_owner(self, owner_id: UUID) -> list[Category]: ...

    async def find_by_name(
        self, owner_id: UUID, comparable: str, kind: TransactionKind
    ) -> Category | None:
        """Para no tener dos categorías que solo se diferencian por mayúsculas."""
        ...

    async def save(self, category: Category) -> None: ...

    async def delete(self, category_id: UUID, owner_id: UUID) -> None: ...


class AccountGateway(Protocol):
    """La vista que movimientos tiene de una cuenta, por la aplicación de cuentas."""

    async def target(self, account_id: UUID, owner_id: UUID) -> TargetAccount | None:
        """None si no existe o si es de otra persona."""
        ...


class IdempotencyStore(Protocol):
    async def remember(
        self, owner_id: UUID, key: str, fingerprint: str, transaction_id: UUID
    ) -> None: ...

    async def recall(self, owner_id: UUID, key: str) -> tuple[str, UUID] | None:
        """La huella y el movimiento que creó esa clave, si ya se usó."""
        ...

    async def forget_expired(self, before: datetime) -> None: ...


class AuditLog(Protocol):
    """Append-only: solo se agrega (ADR-0011). La base rechaza actualizar y borrar."""

    async def record(self, action: AuditAction, transaction: Transaction, at: datetime) -> None: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class DatabaseTransaction(Protocol):
    """La transacción de la base: nada que ver con un movimiento de plata."""

    async def commit(self) -> None: ...
