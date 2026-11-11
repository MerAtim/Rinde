"""Arma las cotizaciones: la cadena de fuentes con su caché, y la unidad de trabajo."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rinde.rates.application.ports import Clock, RateHistoryProvider, RateProvider
from rinde.rates.application.providers import (
    CachedHistoryProvider,
    CachedRateProvider,
    FallbackRateProvider,
)
from rinde.rates.application.unit import RatesUnit, build_rates_unit
from rinde.rates.application.use_cases import RatesDependencies
from rinde.rates.infrastructure.repositories import SqlAlchemyQuoteRepository
from rinde.rates.infrastructure.sources import (
    ArgentinaDatosProvider,
    CriptoYaProvider,
    DolarApiProvider,
)

CACHE_TTL = timedelta(minutes=15)


def build_rate_provider(
    client: httpx.AsyncClient,
    clock: Clock,
    *,
    dolarapi_url: str,
    argentinadatos_url: str,
    criptoya_url: str,
) -> RateProvider:
    """El orden es el de la cadena (ADR-0016).

    ArgentinaDatos va segunda y no última: es del mismo autor que DolarAPI, pero
    es la única, además de DolarAPI, que publica el MEP, el CCL, el tarjeta y el
    cripto. CriptoYa queda al final porque solo cubre el oficial y el blue.
    """
    chain = FallbackRateProvider(
        [
            ("dolarapi", DolarApiProvider(client, clock, base_url=dolarapi_url)),
            ("argentinadatos", ArgentinaDatosProvider(client, base_url=argentinadatos_url)),
            ("criptoya", CriptoYaProvider(client, clock, base_url=criptoya_url)),
        ]
    )
    return CachedRateProvider(chain, clock, ttl=CACHE_TTL)


def build_history_provider(
    client: httpx.AsyncClient, clock: Clock, *, argentinadatos_url: str
) -> RateHistoryProvider:
    """Solo ArgentinaDatos publica la serie completa de cada dólar (ADR-0018).

    Sin respaldo: si no responde, los días que faltan quedan sin cotización y
    la pantalla lo dice. Se vuelve a probar en el pedido siguiente.
    """
    return CachedHistoryProvider(
        ArgentinaDatosProvider(client, base_url=argentinadatos_url), clock, ttl=CACHE_TTL
    )


class SqlAlchemyTransaction:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()


class SqlAlchemyRatesUnitFactory:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        provider: RateProvider,
        history: RateHistoryProvider,
        clock: Clock,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._provider = provider
        self._history = history
        self._clock = clock

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[RatesUnit]:
        async with self._sessionmaker() as session:
            yield build_rates_unit(
                RatesDependencies(
                    quotes=SqlAlchemyQuoteRepository(session),
                    provider=self._provider,
                    history=self._history,
                    transaction=SqlAlchemyTransaction(session),
                    clock=self._clock,
                )
            )
