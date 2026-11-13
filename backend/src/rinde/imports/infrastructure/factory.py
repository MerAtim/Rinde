"""Crea la unidad de trabajo de importación sobre PostgreSQL, una por pedido."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rinde.imports.application.ports import Clock
from rinde.imports.application.unit import ImportsGateways, ImportsUnit, build_imports_unit
from rinde.imports.infrastructure.repositories import (
    SqlAlchemyBatchRepository,
    SqlAlchemyRuleRepository,
)


class SqlAlchemyTransaction:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()


class SqlAlchemyImportsUnitFactory:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        gateways: ImportsGateways,
        clock: Clock,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._gateways = gateways
        self._clock = clock

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[ImportsUnit]:
        async with self._sessionmaker() as session:
            yield build_imports_unit(
                SqlAlchemyBatchRepository(session),
                SqlAlchemyRuleRepository(session),
                SqlAlchemyTransaction(session),
                self._gateways,
                self._clock,
            )
