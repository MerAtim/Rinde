"""Puertos de importación.

Los lotes son propios. La cuenta, sus movimientos y las categorías son de
movimientos: se leen y se escriben por su capa de aplicación, con adaptadores
que arma la raíz de composición (ADR-0018), como hacen presupuestos y alertas.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from rinde.imports.domain.batch import AccountState, ImportBatch
from rinde.imports.domain.statement import Statement


class StatementReader(Protocol):
    """Un formato de archivo (patrón Strategy): bytes adentro, líneas afuera."""

    def read(self, content: bytes) -> Statement: ...


class BatchRepository(Protocol):
    async def add(self, batch: ImportBatch) -> None: ...

    async def get(self, batch_id: UUID, owner_id: UUID) -> ImportBatch | None:
        """Solo los del dueño, con sus líneas."""
        ...

    async def save_confirmation(self, batch: ImportBatch) -> None:
        """Guarda cuándo se confirmó y cuántas líneas entraron."""
        ...

    async def delete(self, batch_id: UUID, owner_id: UUID) -> bool:
        """Solo sin confirmar. `False` si no había nada que borrar."""
        ...

    async def delete_expired(self, now: datetime) -> None:
        """Los vencidos sin confirmar, de cualquier persona: el archivo ya no sirve."""
        ...


class AccountInspector(Protocol):
    async def inspect(
        self, owner_id: UUID, account_id: UUID, fingerprints: list[str], period: tuple[date, date]
    ) -> AccountState:
        """Falla si la cuenta no es del dueño o está archivada."""
        ...


@dataclass(frozen=True, slots=True)
class LineToRegister:
    signed_amount: Decimal
    category_id: UUID
    occurred_on: date
    description: str | None
    fingerprint: str


@dataclass(frozen=True, slots=True)
class Registered:
    imported: int
    skipped: int


class MovementRegistrar(Protocol):
    async def register(
        self, owner_id: UUID, account_id: UUID, lines: list[LineToRegister]
    ) -> Registered:
        """Todas o ninguna, en una sola transacción de movimientos."""
        ...


@dataclass(frozen=True, slots=True)
class CategoryInfo:
    id: UUID
    slug: str | None
    is_expense: bool


class CategoryReader(Protocol):
    async def categories(self, owner_id: UUID) -> list[CategoryInfo]: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...
