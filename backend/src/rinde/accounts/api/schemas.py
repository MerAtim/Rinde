"""Esquemas de entrada y salida de cuentas.

La validación del borde es gruesa (tipos, largo máximo, campos desconocidos);
las reglas finas, como los caracteres invisibles o Bitcoin solo en billeteras
cripto, las decide el dominio.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from rinde.accounts.domain.account import Account, AccountKind, AccountName
from rinde.shared.domain.money import Currency


class OpenAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=AccountName.MAX_LENGTH)
    kind: AccountKind
    currency: Currency


class RenameAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=AccountName.MAX_LENGTH)


class AccountResponse(BaseModel):
    id: UUID
    name: str
    kind: AccountKind
    currency: Currency
    created_at: datetime
    archived_at: datetime | None

    @classmethod
    def from_account(cls, account: Account) -> AccountResponse:
        return cls(
            id=account.id,
            name=account.name.value,
            kind=account.kind,
            currency=account.currency,
            created_at=account.created_at,
            archived_at=account.archived_at,
        )
