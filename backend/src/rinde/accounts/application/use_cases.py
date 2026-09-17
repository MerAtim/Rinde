"""Casos de uso de cuentas. Todos reciben el dueño: es el filtro de autorización."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from rinde.accounts.application.ports import AccountRepository, Clock, Transaction
from rinde.accounts.domain.account import Account, AccountKind, AccountName
from rinde.accounts.domain.errors import AccountNotFoundError
from rinde.shared.domain.money import Currency


@dataclass(frozen=True, slots=True)
class AccountsDependencies:
    accounts: AccountRepository
    transaction: Transaction
    clock: Clock


async def _owned(deps: AccountsDependencies, account_id: UUID, owner_id: UUID) -> Account:
    account = await deps.accounts.get(account_id, owner_id)
    if account is None:
        raise AccountNotFoundError
    return account


class OpenAccount:
    def __init__(self, deps: AccountsDependencies) -> None:
        self._deps = deps

    async def execute(
        self, owner_id: UUID, raw_name: str, kind: AccountKind, currency: Currency
    ) -> Account:
        deps = self._deps
        account = Account(
            id=uuid4(),
            owner_id=owner_id,
            name=AccountName.parse(raw_name),
            kind=kind,
            currency=currency,
            created_at=deps.clock.now(),
        )
        await deps.accounts.add(account)
        await deps.transaction.commit()
        return account


class ListAccounts:
    def __init__(self, deps: AccountsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, *, include_archived: bool = False) -> list[Account]:
        return await self._deps.accounts.list_for_owner(owner_id, include_archived=include_archived)


class GetAccount:
    def __init__(self, deps: AccountsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, account_id: UUID) -> Account:
        return await _owned(self._deps, account_id, owner_id)


class RenameAccount:
    def __init__(self, deps: AccountsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, account_id: UUID, raw_name: str) -> Account:
        deps = self._deps
        account = (await _owned(deps, account_id, owner_id)).renamed(AccountName.parse(raw_name))
        await deps.accounts.save(account)
        await deps.transaction.commit()
        return account


class ArchiveAccount:
    def __init__(self, deps: AccountsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, account_id: UUID) -> Account:
        deps = self._deps
        current = await _owned(deps, account_id, owner_id)
        account = current.archived(deps.clock.now())
        if account is not current:
            await deps.accounts.save(account)
            await deps.transaction.commit()
        return account
