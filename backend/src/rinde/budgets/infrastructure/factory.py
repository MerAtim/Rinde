"""Crea la unidad de trabajo de presupuestos sobre PostgreSQL, una por pedido."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rinde.budgets.application.ports import Clock
from rinde.budgets.application.unit import BudgetsGateways, BudgetsUnit, build_budgets_unit
from rinde.budgets.infrastructure.repositories import SqlAlchemyBudgetRepository


class SqlAlchemyTransaction:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()


class SqlAlchemyBudgetsUnitFactory:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        gateways: BudgetsGateways,
        clock: Clock,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._gateways = gateways
        self._clock = clock

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[BudgetsUnit]:
        async with self._sessionmaker() as session:
            yield build_budgets_unit(
                SqlAlchemyBudgetRepository(session),
                SqlAlchemyTransaction(session),
                self._gateways,
                self._clock,
            )
