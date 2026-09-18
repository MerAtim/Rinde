"""La cuenta: dónde está la plata, en qué moneda y de quién es (ADR-0009)."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from rinde.accounts.domain.errors import (
    AccountArchivedError,
    AccountCurrencyNotAllowedError,
    AccountNameInvalidError,
)
from rinde.shared.domain.money import Currency
from rinde.shared.domain.text import is_clean, normalize


class AccountKind(StrEnum):
    CASH = "cash"
    BANK = "bank"
    CREDIT_CARD = "credit_card"
    CRYPTO_WALLET = "crypto_wallet"


@dataclass(frozen=True, slots=True)
class AccountName:
    """Nombre que elige la persona, como "Galicia sueldo" o "Billetera Lemon"."""

    MAX_LENGTH: ClassVar[int] = 60
    value: str

    @classmethod
    def parse(cls, raw: str) -> AccountName:
        value = normalize(raw)
        if not 1 <= len(value) <= cls.MAX_LENGTH or not is_clean(value):
            raise AccountNameInvalidError
        return cls(value)


@dataclass(frozen=True, slots=True)
class Account:
    id: UUID
    owner_id: UUID
    name: AccountName
    kind: AccountKind
    currency: Currency
    """Fija desde que se abre: cambiarla reinterpretaría los montos históricos."""
    created_at: datetime
    archived_at: datetime | None = None

    def __post_init__(self) -> None:
        # En toda cuenta, no solo al abrirla: también la que se lee de la base.
        if self.currency is Currency.BTC and self.kind is not AccountKind.CRYPTO_WALLET:
            raise AccountCurrencyNotAllowedError

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    def renamed(self, name: AccountName) -> Account:
        if self.is_archived:
            raise AccountArchivedError
        return replace(self, name=name)

    def archived(self, at: datetime) -> Account:
        """Idempotente: archivar dos veces conserva la primera fecha."""
        return self if self.is_archived else replace(self, archived_at=at)
