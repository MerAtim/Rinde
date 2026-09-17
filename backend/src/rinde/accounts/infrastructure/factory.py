"""Crea la unidad de trabajo de cuentas sobre PostgreSQL, una por pedido."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rinde.accounts.application.ports import Clock
from rinde.accounts.application.unit import AccountsUnit, build_accounts_unit
from rinde.accounts.application.use_cases import AccountsDependencies
from rinde.accounts.infrastructure.repositories import SqlAlchemyAccountRepository


class SqlAlchemyTransaction:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()


class SqlAlchemyAccountsUnitFactory:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], clock: Clock) -> None:
        self._sessionmaker = sessionmaker
        self._clock = clock

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AccountsUnit]:
        # Si el pedido falla antes de confirmar, al cerrar la sesión se descarta la transacción.
        async with self._sessionmaker() as session:
            yield build_accounts_unit(
                AccountsDependencies(
                    accounts=SqlAlchemyAccountRepository(session),
                    transaction=SqlAlchemyTransaction(session),
                    clock=self._clock,
                )
            )
