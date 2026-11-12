"""Crea la unidad de trabajo de alertas sobre PostgreSQL, una por pedido."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rinde.alerts.application.ports import Clock
from rinde.alerts.application.unit import AlertsGateways, AlertsUnit, build_alerts_unit
from rinde.alerts.infrastructure.repositories import SqlAlchemyAlertRepository


class SqlAlchemyTransaction:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()


class SqlAlchemyAlertsUnitFactory:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        gateways: AlertsGateways,
        clock: Clock,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._gateways = gateways
        self._clock = clock

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AlertsUnit]:
        async with self._sessionmaker() as session:
            yield build_alerts_unit(
                SqlAlchemyAlertRepository(session),
                SqlAlchemyTransaction(session),
                self._gateways,
                self._clock,
            )
