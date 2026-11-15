"""Puertos de la demo: lo que hace falta para sembrar una cuenta, sin decir cómo.

Los tipos son propios y simples: la demo no importa el dominio de ningún otro
módulo. El adaptador los traduce a los casos de uso de cada uno.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from rinde.shared.domain.money import Currency, Money


class AccountType(StrEnum):
    BANK = "bank"
    CASH = "cash"
    CREDIT_CARD = "credit_card"


class EntryKind(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"


@dataclass(frozen=True, slots=True)
class Entry:
    account_id: UUID
    kind: EntryKind
    amount: Decimal
    category_id: UUID
    on: date
    description: str


@dataclass(frozen=True, slots=True)
class TransferEntry:
    from_account_id: UUID
    to_account_id: UUID
    sent: Decimal
    received: Decimal
    on: date
    description: str


@dataclass(frozen=True, slots=True)
class PlanEntry:
    account_id: UUID
    category_id: UUID
    total: Decimal
    count: int
    first_on: date
    description: str


@dataclass(frozen=True, slots=True)
class RuleEntry:
    """Siempre mensual: es lo que más se repite en la vida real."""

    account_id: UUID
    kind: EntryKind
    amount: Decimal
    category_id: UUID
    starts_on: date
    description: str


class DemoWriter(Protocol):
    async def open_account(
        self, owner_id: UUID, name: str, kind: AccountType, currency: Currency
    ) -> UUID: ...

    async def categories(self, owner_id: UUID) -> dict[str, UUID]:
        """Las categorías sembradas de la cuenta, por su slug."""
        ...

    async def set_budget(self, owner_id: UUID, category_id: UUID, limit: Money) -> None: ...

    async def record(self, owner_id: UUID, entry: Entry) -> None: ...

    async def transfer(self, owner_id: UUID, entry: TransferEntry) -> None: ...

    async def installments(self, owner_id: UUID, entry: PlanEntry) -> None: ...

    async def recurring(self, owner_id: UUID, entry: RuleEntry) -> None: ...


class Clock(Protocol):
    def now(self) -> datetime: ...
