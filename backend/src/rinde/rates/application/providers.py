"""Cómo se combinan las fuentes: respaldo entre fuentes y caché (ADR-0016).

Las dos piezas implementan el mismo puerto que una fuente, así que se apilan
sin que el caso de uso se entere: caché, después la cadena y, al final, las
fuentes.
"""

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from rinde.rates.application.ports import (
    Clock,
    QuoteRequest,
    RateHistoryProvider,
    RateProvider,
    RateSourceUnavailableError,
)
from rinde.rates.domain.quote import Market, Quote, QuoteKind

logger = logging.getLogger(__name__)


class FallbackRateProvider:
    """Cadena de responsabilidad: cada fuente completa lo que la anterior no tuvo.

    Si una fuente no responde, o no tiene un tipo de dólar, ese tipo se le pide
    a la siguiente. Nunca se reemplaza un tipo por otro: cada fuente solo
    devuelve los tipos que publica con la misma definición.
    """

    def __init__(self, providers: Sequence[tuple[str, RateProvider]]) -> None:
        self._providers = tuple(providers)

    async def quotes(self, request: QuoteRequest) -> dict[QuoteKind, Quote]:
        found: dict[QuoteKind, Quote] = {}
        answered = False
        for name, provider in self._providers:
            missing = request.types - found.keys()
            if not missing:
                break
            try:
                result = await provider.quotes(replace(request, types=missing))
            except RateSourceUnavailableError:
                logger.warning("La fuente de cotizaciones %s no respondió", name, exc_info=True)
                continue
            answered = True
            # Una fuente que devuelve de más, u otro día, no ensucia el resultado.
            found |= {
                rate_type: quote
                for rate_type, quote in result.items()
                if rate_type in missing
                and quote.rate_type is rate_type
                and quote.day == request.day
            }
        if not answered:
            raise RateSourceUnavailableError
        return found


@dataclass(frozen=True, slots=True)
class _Entry:
    expires_at: datetime
    quote: Quote | None
    """`None` también se guarda: que una fuente no tenga un dato no cambia en minutos."""


class CachedRateProvider:
    """Decorador: guarda en memoria lo que respondieron las fuentes durante un rato.

    Las fuentes no publican términos de uso ni límites, así que se les pregunta
    lo menos posible. Un error no se guarda: el pedido siguiente vuelve a probar.

    Un solo candado para todos los pedidos: mientras uno consulta las fuentes,
    los demás esperan y después leen lo que trajo, en vez de salir todos juntos
    a preguntar lo mismo.
    """

    def __init__(
        self, inner: RateProvider, clock: Clock, *, ttl: timedelta, max_entries: int = 2048
    ) -> None:
        self._inner = inner
        self._clock = clock
        self._ttl = ttl
        self._max_entries = max_entries
        self._entries: dict[tuple[QuoteRequest, QuoteKind], _Entry] = {}
        self._lock = asyncio.Lock()

    async def quotes(self, request: QuoteRequest) -> dict[QuoteKind, Quote]:
        async with self._lock:
            now = self._clock.now()
            hits: dict[QuoteKind, Quote] = {}
            misses: set[QuoteKind] = set()
            for rate_type in request.types:
                entry = self._entries.get((self._key(request), rate_type))
                if entry is None or entry.expires_at <= now:
                    misses.add(rate_type)
                elif entry.quote is not None:
                    hits[rate_type] = entry.quote
            if not misses:
                return hits
            fetched = await self._inner.quotes(replace(request, types=frozenset(misses)))
            self._forget_expired(now)
            for rate_type in misses:
                self._entries[(self._key(request), rate_type)] = _Entry(
                    now + self._ttl, fetched.get(rate_type)
                )
            return hits | {t: q for t, q in fetched.items() if t in misses}

    @staticmethod
    def _key(request: QuoteRequest) -> QuoteRequest:
        """Cada tipo se guarda por separado: la clave no depende de qué otros se pidieron."""
        return replace(request, types=frozenset())

    def _forget_expired(self, now: datetime) -> None:
        self._entries = {k: e for k, e in self._entries.items() if e.expires_at > now}
        # Un tope por si alguien recorre miles de fechas en pocos minutos.
        while len(self._entries) >= self._max_entries:
            del self._entries[next(iter(self._entries))]


class CachedHistoryProvider:
    """Decorador: la última serie de cada dólar o mercado, en memoria un rato (ADR-0018).

    Una serie pesa unos cientos de KB y solo cambia una vez por día. Sin esto,
    un período con días que la fuente no tiene (antes de 2018, por ejemplo)
    pediría la serie entera en cada pedido. Un error no se guarda.
    """

    def __init__(self, inner: RateHistoryProvider, clock: Clock, *, ttl: timedelta) -> None:
        self._inner = inner
        self._clock = clock
        self._ttl = ttl
        self._entries: dict[QuoteKind, tuple[datetime, list[Quote]]] = {}
        self._lock = asyncio.Lock()

    async def series(self, rate_type: QuoteKind) -> list[Quote]:
        async with self._lock:
            now = self._clock.now()
            entry = self._entries.get(rate_type)
            if entry is not None and entry[0] > now:
                return entry[1]
            series = await self._inner.series(rate_type)
            # Una por clase: seis dólares y un mercado, no hace falta tope.
            self._entries[rate_type] = (now + self._ttl, series)
            return series


class FallbackHistoryProvider:
    """Cadena de responsabilidad para las series: si una fuente no responde, la siguiente.

    A diferencia del precio de hoy, una serie no se completa entre fuentes: se
    toma entera de la primera que responda con algo, para que los días de un
    rango no salgan de fuentes distintas sin motivo.
    """

    def __init__(self, providers: Sequence[tuple[str, RateHistoryProvider]]) -> None:
        self._providers = tuple(providers)

    async def series(self, rate_type: QuoteKind) -> list[Quote]:
        for name, provider in self._providers:
            try:
                series = await provider.series(rate_type)
            except RateSourceUnavailableError:
                logger.warning("La fuente de series %s no respondió", name, exc_info=True)
                continue
            if series:
                return series
        raise RateSourceUnavailableError


class RoutingRateProvider:
    """Manda cada clase a su cadena: los dólares a la suya, los mercados a la suya (ADR-0029).

    Así una fuente de dólares nunca recibe un pedido del Bitcoin, ni al revés.
    """

    def __init__(self, dollars: RateProvider, markets: RateProvider) -> None:
        self._dollars = dollars
        self._markets = markets

    async def quotes(self, request: QuoteRequest) -> dict[QuoteKind, Quote]:
        markets = frozenset(kind for kind in request.types if isinstance(kind, Market))
        dollars = request.types - markets
        found: dict[QuoteKind, Quote] = {}
        failures = 0
        for provider, kinds in ((self._dollars, dollars), (self._markets, markets)):
            if not kinds:
                continue
            try:
                found |= await provider.quotes(replace(request, types=kinds))
            except RateSourceUnavailableError:
                failures += 1
        # Caída es que no haya respondido ninguna de las cadenas que se usaron.
        if failures and failures == bool(dollars) + bool(markets):
            raise RateSourceUnavailableError
        return found


class RoutingHistoryProvider:
    """Lo mismo que `RoutingRateProvider`, para las series."""

    def __init__(self, dollars: RateHistoryProvider, markets: RateHistoryProvider) -> None:
        self._dollars = dollars
        self._markets = markets

    async def series(self, rate_type: QuoteKind) -> list[Quote]:
        provider = self._markets if isinstance(rate_type, Market) else self._dollars
        return await provider.series(rate_type)
