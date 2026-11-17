"""Arma las cotizaciones: la cadena de fuentes con su caché, y la unidad de trabajo."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rinde.rates.application.ports import Clock, RateHistoryProvider, RateProvider
from rinde.rates.application.providers import (
    CachedHistoryProvider,
    CachedRateProvider,
    FallbackHistoryProvider,
    FallbackRateProvider,
    RoutingHistoryProvider,
    RoutingRateProvider,
)
from rinde.rates.application.unit import RatesUnit, build_rates_unit
from rinde.rates.application.use_cases import RatesDependencies
from rinde.rates.infrastructure.bitcoin import BitstampProvider, KrakenProvider
from rinde.rates.infrastructure.repositories import SqlAlchemyQuoteRepository
from rinde.rates.infrastructure.sources import (
    ArgentinaDatosProvider,
    CriptoYaProvider,
    DolarApiProvider,
)

CACHE_TTL = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class SourceUrls:
    """Dónde está cada fuente. Configurable para apuntarlas a un doble en pruebas."""

    dolarapi: str
    argentinadatos: str
    criptoya: str
    kraken: str
    bitstamp: str


def build_rate_provider(client: httpx.AsyncClient, clock: Clock, urls: SourceUrls) -> RateProvider:
    """El orden es el de la cadena (ADR-0016). El Bitcoin tiene la suya (ADR-0029).

    ArgentinaDatos va segunda y no última: es del mismo autor que DolarAPI, pero
    es la única, además de DolarAPI, que publica el MEP, el CCL, el tarjeta y el
    cripto. CriptoYa queda al final porque solo cubre el oficial y el blue.
    """
    dollars = FallbackRateProvider(
        [
            ("dolarapi", DolarApiProvider(client, clock, base_url=urls.dolarapi)),
            ("argentinadatos", ArgentinaDatosProvider(client, base_url=urls.argentinadatos)),
            ("criptoya", CriptoYaProvider(client, clock, base_url=urls.criptoya)),
        ]
    )
    bitcoin = FallbackRateProvider(
        [
            ("kraken", KrakenProvider(client, base_url=urls.kraken)),
            ("bitstamp", BitstampProvider(client, clock, base_url=urls.bitstamp)),
        ]
    )
    return CachedRateProvider(RoutingRateProvider(dollars, bitcoin), clock, ttl=CACHE_TTL)


def build_history_provider(
    client: httpx.AsyncClient, clock: Clock, urls: SourceUrls
) -> RateHistoryProvider:
    """Solo ArgentinaDatos publica la serie completa de cada dólar (ADR-0018).

    Sin respaldo para los dólares: si no responde, los días que faltan quedan
    sin cotización y la pantalla lo dice. Se vuelve a probar en el pedido
    siguiente. El Bitcoin sí tiene respaldo: Kraken y Bitstamp (ADR-0029).
    """
    bitcoin = FallbackHistoryProvider(
        [
            ("kraken", KrakenProvider(client, base_url=urls.kraken)),
            ("bitstamp", BitstampProvider(client, clock, base_url=urls.bitstamp)),
        ]
    )
    return CachedHistoryProvider(
        RoutingHistoryProvider(
            ArgentinaDatosProvider(client, base_url=urls.argentinadatos), bitcoin
        ),
        clock,
        ttl=CACHE_TTL,
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
