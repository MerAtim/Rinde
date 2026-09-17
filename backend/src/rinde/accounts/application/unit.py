"""Unidad de trabajo de cuentas: los casos de uso de un pedido, con una transacción."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from rinde.accounts.application.use_cases import (
    AccountsDependencies,
    ArchiveAccount,
    GetAccount,
    ListAccounts,
    OpenAccount,
    RenameAccount,
)


@dataclass(frozen=True, slots=True)
class AccountsUnit:
    open: OpenAccount
    list: ListAccounts
    get: GetAccount
    rename: RenameAccount
    archive: ArchiveAccount


class AccountsUnitFactory(Protocol):
    """La raíz de composición elige la implementación: base real o memoria en tests."""

    def __call__(self) -> AbstractAsyncContextManager[AccountsUnit]: ...


def build_accounts_unit(deps: AccountsDependencies) -> AccountsUnit:
    return AccountsUnit(
        open=OpenAccount(deps),
        list=ListAccounts(deps),
        get=GetAccount(deps),
        rename=RenameAccount(deps),
        archive=ArchiveAccount(deps),
    )
