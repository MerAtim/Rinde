"""Repositorio de cuentas sobre PostgreSQL. No confirma: lo hace la transacción."""

from uuid import UUID

from sqlalchemy import RowMapping, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rinde.accounts.domain.account import Account, AccountKind, AccountName
from rinde.accounts.infrastructure.tables import accounts
from rinde.shared.domain.money import Currency


def _to_account(row: RowMapping) -> Account:
    return Account(
        id=row["id"],
        owner_id=row["owner_id"],
        name=AccountName(row["name"]),
        kind=AccountKind(row["kind"]),
        currency=Currency(row["currency"]),
        created_at=row["created_at"],
        archived_at=row["archived_at"],
    )


class SqlAlchemyAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, account: Account) -> None:
        await self._session.execute(
            insert(accounts).values(
                id=account.id,
                owner_id=account.owner_id,
                name=account.name.value,
                kind=account.kind.value,
                currency=account.currency.value,
                created_at=account.created_at,
                archived_at=account.archived_at,
            )
        )

    async def get(self, account_id: UUID, owner_id: UUID) -> Account | None:
        result = await self._session.execute(
            select(accounts).where(accounts.c.id == account_id, accounts.c.owner_id == owner_id)
        )
        row = result.mappings().one_or_none()
        return _to_account(row) if row else None

    async def list_for_owner(self, owner_id: UUID, *, include_archived: bool) -> list[Account]:
        query = select(accounts).where(accounts.c.owner_id == owner_id)
        if not include_archived:
            query = query.where(accounts.c.archived_at.is_(None))
        result = await self._session.execute(query.order_by(accounts.c.created_at, accounts.c.id))
        return [_to_account(row) for row in result.mappings()]

    async def save(self, account: Account) -> None:
        # La moneda, el tipo y el dueño no se actualizan: son fijos (ADR-0009).
        await self._session.execute(
            update(accounts)
            .where(accounts.c.id == account.id, accounts.c.owner_id == account.owner_id)
            .values(name=account.name.value, archived_at=account.archived_at)
        )
