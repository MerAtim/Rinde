"""Arma el módulo de inflación: la fuente con su caché, y la unidad de trabajo."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rinde.inflation.application.ports import Clock, CpiProvider
from rinde.inflation.application.providers import CachedCpiProvider
from rinde.inflation.application.unit import InflationUnit, build_inflation_unit
from rinde.inflation.application.use_cases import InflationDependencies
from rinde.inflation.infrastructure.repositories import SqlAlchemyCpiRepository
from rinde.inflation.infrastructure.source import DatosGobArCpiProvider

CACHE_TTL = timedelta(hours=1)
"""El IPC se publica una vez por mes: una hora no deja esperando un dato nuevo (ADR-0025)."""


def build_cpi_provider(client: httpx.AsyncClient, clock: Clock, *, base_url: str) -> CpiProvider:
    """Sin respaldo: si la fuente no responde, se usa lo guardado y lo nuevo queda vacío."""
    return CachedCpiProvider(DatosGobArCpiProvider(client, base_url=base_url), clock, ttl=CACHE_TTL)


class SqlAlchemyTransaction:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()


class SqlAlchemyInflationUnitFactory:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        provider: CpiProvider,
        clock: Clock,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._provider = provider
        self._clock = clock

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[InflationUnit]:
        async with self._sessionmaker() as session:
            yield build_inflation_unit(
                InflationDependencies(
                    months=SqlAlchemyCpiRepository(session),
                    provider=self._provider,
                    transaction=SqlAlchemyTransaction(session),
                    clock=self._clock,
                )
            )
