"""Puertos del módulo de movimientos.

Como en cuentas, ninguna lectura acepta solo un identificador: siempre pide
también el dueño, así un caso de uso no puede olvidarse de filtrar por el
usuario autenticado. Y ningún listado devuelve movimientos borrados (ADR-0011).
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from rinde.shared.domain.money import Currency, Money
from rinde.transactions.domain.category import Category, TransactionKind
from rinde.transactions.domain.transaction import AuditAction, TargetAccount, Transaction
from rinde.transactions.domain.transfer import Transfer


@dataclass(frozen=True, slots=True)
class TransactionFilters:
    """Lo que la lista puede acotar. Todo opcional: sin nada, son todos."""

    account_id: UUID | None = None
    since: date | None = None
    until: date | None = None
    category_id: UUID | None = None
    text: str | None = None
    """Busca en la descripción, sin distinguir tildes ni mayúsculas."""


@dataclass(frozen=True, slots=True)
class Page:
    """Una porción de la lista, con la marca para pedir la siguiente."""

    items: list[Transaction]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class TransferFilters:
    """Lo que la lista puede acotar.

    `account_id` alcanza a la cuenta esté de un lado o del otro: quien mira una
    cuenta quiere ver tanto lo que le entró como lo que le salió.
    """

    account_id: UUID | None = None
    since: date | None = None
    until: date | None = None
    text: str | None = None
    """Busca en la descripción. Una transferencia no tiene categoría por la que filtrar."""


@dataclass(frozen=True, slots=True)
class TransferPage:
    items: list[Transfer]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class HistoryPage:
    """Movimientos y transferencias en una sola línea de tiempo.

    Las dos cosas se ordenan por el mismo par `(occurred_on, id)`, que es lo que
    permite intercalarlas con un solo cursor (ADR-0014, decisión 5).
    """

    items: list[Transaction | Transfer]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class AccountBalance:
    account_id: UUID
    balance: Money


@dataclass(frozen=True, slots=True)
class LedgerScope:
    """Qué parte del libro se resume: un período y, si se elige, algunas cuentas.

    Una cuenta ajena en `account_ids` no agrega nada: toda consulta filtra
    además por el dueño (ADR-0009).
    """

    since: date
    until: date
    account_ids: frozenset[UUID] | None = None
    """`None` son todas las cuentas."""
    monthly_currency: Currency | None = None
    """Los flujos en esta moneda se suman por mes y no por día.

    Es la moneda en que se muestran los totales: no se convierte, así que el día
    no hace falta, y sumar por mes devuelve muchas menos filas (ADR-0018).
    """


@dataclass(frozen=True, slots=True)
class FlowSum:
    """Lo que suma la base: un día, un tipo, una categoría y una moneda.

    En la moneda de `monthly_currency`, `day` es el primer día del mes.

    Sin el nombre de la categoría: repetirlo en miles de filas cuesta más que
    pedir las categorías aparte, que son unas pocas.
    """

    day: date
    kind: TransactionKind
    category_id: UUID
    total: Money


@dataclass(frozen=True, slots=True)
class FlowTotal:
    """Lo que entró o salió un día en una categoría, en una moneda. Sin transferencias."""

    day: date
    kind: TransactionKind
    category_id: UUID
    category_name: str
    category_slug: str | None
    total: Money


@dataclass(frozen=True, slots=True)
class BalanceChange:
    """Cuánto cambió el saldo de una cuenta en un mes, con movimientos y transferencias.

    Por mes y no por día: el patrimonio se mira al cierre de cada mes, y lo de
    adentro del mes no cambia ese cierre. `month` es el primer día del mes; en
    `None` es todo lo anterior al período junto, el saldo de apertura.
    """

    account_id: UUID
    month: date | None
    change: Money


@dataclass(frozen=True, slots=True)
class LedgerSummary:
    flows: list[FlowTotal]
    balance_changes: list[BalanceChange]


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

    async def flow_sums(self, owner_id: UUID, scope: LedgerScope) -> list[FlowSum]:
        """Sumas por día, tipo, categoría y moneda del período, sin los borrados."""
        ...

    async def balance_changes(self, owner_id: UUID, scope: LedgerScope) -> list[BalanceChange]:
        """Cambio de saldo por cuenta y mes hasta `until`; lo anterior a `since`, junto."""
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


class IdempotentResource(StrEnum):
    """Qué creó una clave de idempotencia.

    Se guarda en lugar de deducirlo: la misma clave usada para un movimiento y
    para una transferencia tiene que fallar de forma evidente, no depender de
    que las huellas casualmente no coincidan.
    """

    TRANSACTION = "transaction"
    TRANSFER = "transfer"


@dataclass(frozen=True, slots=True)
class RememberedKey:
    """Lo que dejó una clave ya usada: qué pedido era y qué creó."""

    fingerprint: str
    resource: IdempotentResource
    resource_id: UUID


class IdempotencyStore(Protocol):
    async def remember(
        self, owner_id: UUID, key: str, remembered: RememberedKey, at: datetime
    ) -> None: ...

    async def recall(self, owner_id: UUID, key: str) -> RememberedKey | None:
        """Lo que creó esa clave, si ya se usó."""
        ...

    async def forget_expired(self, before: datetime) -> None: ...


class TransferRepository(Protocol):
    async def add(self, transfer: Transfer) -> None: ...

    async def get(self, transfer_id: UUID, owner_id: UUID) -> Transfer | None:
        """Devuelve también la borrada: hace falta para deshacer."""
        ...

    async def page_for_owner(
        self, owner_id: UUID, filters: TransferFilters, *, cursor: str | None, limit: int
    ) -> TransferPage:
        """De la más reciente a la más vieja, sin las borradas."""
        ...

    async def balances_for_owner(self, owner_id: UUID) -> list[AccountBalance]:
        """Lo que cada cuenta recibió menos lo que envió, sin las borradas."""
        ...

    async def balance_changes(self, owner_id: UUID, scope: LedgerScope) -> list[BalanceChange]:
        """Como en movimientos: cada lado de una transferencia cambia el saldo de su cuenta."""
        ...

    async def save(self, transfer: Transfer) -> None: ...


class AuditLog(Protocol):
    """Append-only: solo se agrega (ADR-0011). La base rechaza actualizar y borrar."""

    async def record(self, action: AuditAction, transaction: Transaction, at: datetime) -> None: ...


class TransferAuditLog(Protocol):
    """Append-only, igual que el de movimientos (ADR-0014, decisión 4)."""

    async def record(self, action: AuditAction, transfer: Transfer, at: datetime) -> None: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class DatabaseTransaction(Protocol):
    """La transacción de la base: nada que ver con un movimiento de plata."""

    async def commit(self) -> None: ...
