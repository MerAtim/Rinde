"""Crea la unidad de trabajo de movimientos sobre PostgreSQL, una por pedido."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rinde.transactions.application.dependencies import TransactionsDependencies
from rinde.transactions.application.ports import AccountGateway, Clock
from rinde.transactions.application.unit import TransactionsUnit, build_transactions_unit
from rinde.transactions.infrastructure.repositories import (
    SqlAlchemyAuditLog,
    SqlAlchemyCategoryRepository,
    SqlAlchemyIdempotencyStore,
    SqlAlchemyTransactionRepository,
    SqlAlchemyTransferAuditLog,
    SqlAlchemyTransferRepository,
)


class SqlAlchemyDatabaseTransaction:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()


class SqlAlchemyTransactionsUnitFactory:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        clock: Clock,
        # La arma la raíz de composición: movimientos no conoce la infraestructura
        # de cuentas, solo el puerto. Recibe la sesión para leer la cuenta dentro
        # de la misma transacción del pedido.
        account_gateway: Callable[[AsyncSession], AccountGateway],
    ) -> None:
        self._sessionmaker = sessionmaker
        self._clock = clock
        self._account_gateway = account_gateway

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[TransactionsUnit]:
        # Si el pedido falla antes de confirmar, al cerrar la sesión se descarta la transacción.
        async with self._sessionmaker() as session:
            yield build_transactions_unit(
                TransactionsDependencies(
                    transactions=SqlAlchemyTransactionRepository(session),
                    transfers=SqlAlchemyTransferRepository(session),
                    categories=SqlAlchemyCategoryRepository(session),
                    accounts=self._account_gateway(session),
                    idempotency=SqlAlchemyIdempotencyStore(session),
                    audit=SqlAlchemyAuditLog(session),
                    transfer_audit=SqlAlchemyTransferAuditLog(session),
                    transaction=SqlAlchemyDatabaseTransaction(session),
                    clock=self._clock,
                )
            )
