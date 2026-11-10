"""Casos de uso de cotizaciones.

Las cotizaciones no son de nadie: son las mismas para todos los usuarios, así
que estos casos de uso no reciben el `user_id`. La API igual pide sesión, para
que nadie use Rinde como intermediario gratis contra las fuentes (ADR-0016).
"""

from dataclasses import dataclass
from datetime import date

from rinde.rates.application.ports import (
    Clock,
    QuoteRepository,
    QuoteRequest,
    RateProvider,
    RateSourceUnavailableError,
    Transaction,
)
from rinde.rates.domain.errors import (
    RateDateInFutureError,
    RateNotFoundError,
    RatesUnavailableError,
)
from rinde.rates.domain.quote import Quote, argentine_day
from rinde.shared.domain.rate_type import ALL_RATE_TYPES, RateType

_ORDER = {rate_type: index for index, rate_type in enumerate(RateType)}


@dataclass(frozen=True, slots=True)
class RatesDependencies:
    quotes: QuoteRepository
    provider: RateProvider
    transaction: Transaction
    clock: Clock


class GetQuotes:
    """Las cotizaciones de un día: primero lo guardado, después las fuentes.

    * Un día cerrado no cambia: lo que se trae de una fuente se guarda y la vez
      siguiente sale de la base, sin preguntarle a nadie.
    * Hoy la cotización se sigue moviendo y no se guarda: sale de las fuentes,
      con la caché adelante. Cuando el día cierre, se pide el valor final.
    """

    def __init__(self, deps: RatesDependencies) -> None:
        self._deps = deps

    async def execute(
        self, day: date | None = None, types: frozenset[RateType] = ALL_RATE_TYPES
    ) -> list[Quote]:
        now = self._deps.clock.now()
        today = argentine_day(now)
        day = day or today
        if day > today:
            raise RateDateInFutureError
        current = day == today

        stored = (
            {} if current else {q.rate_type: q for q in await self._deps.quotes.for_day(day, types)}
        )
        missing = types - stored.keys()
        fetched: dict[RateType, Quote] = {}
        if missing:
            try:
                fetched = await self._deps.provider.quotes(QuoteRequest(day, missing, current))
            except RateSourceUnavailableError:
                # Lo guardado sigue sirviendo. Si no hay nada, no hay qué mostrar.
                if not stored:
                    raise RatesUnavailableError from None
            if fetched and not current:
                await self._deps.quotes.add_all(fetched.values(), now)
                await self._deps.transaction.commit()

        quotes = stored | {t: q for t, q in fetched.items() if t in missing}
        return sorted(quotes.values(), key=lambda quote: _ORDER[quote.rate_type])


class GetQuote:
    """Un solo tipo de dólar de un día. Es lo que va a usar una conversión."""

    def __init__(self, deps: RatesDependencies) -> None:
        self._quotes = GetQuotes(deps)

    async def execute(self, rate_type: RateType, day: date | None = None) -> Quote:
        quotes = await self._quotes.execute(day, frozenset({rate_type}))
        if not quotes:
            raise RateNotFoundError
        return quotes[0]
