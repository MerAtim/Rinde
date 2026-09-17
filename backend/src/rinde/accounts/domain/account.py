"""La cuenta: dónde está la plata, en qué moneda y de quién es (ADR-0009)."""

import unicodedata
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
        # NFC para que "Nación" escrito de dos formas distintas sea el mismo texto.
        value = unicodedata.normalize("NFC", raw).strip()
        if not 1 <= len(value) <= cls.MAX_LENGTH:
            raise AccountNameInvalidError
        # Los caracteres de control o invisibles no se ven en pantalla y permiten
        # dos nombres que parecen iguales y no lo son.
        if any(unicodedata.category(char) in {"Cc", "Cf"} for char in value):
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
