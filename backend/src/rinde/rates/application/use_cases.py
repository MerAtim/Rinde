"""Casos de uso de cotizaciones.

Las cotizaciones no son de nadie: son las mismas para todos los usuarios, así
que estos casos de uso no reciben el `user_id`. La API igual pide sesión, para
que nadie use Rinde como intermediario gratis contra las fuentes (ADR-0016).
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from rinde.rates.application.ports import (
    Clock,
    QuoteRepository,
    QuoteRequest,
    RateHistoryProvider,
    RateProvider,
    RateSourceUnavailableError,
    Transaction,
)
from rinde.rates.domain.conversion import Conversion, convert, route
from rinde.rates.domain.errors import (
    ConversionSameCurrencyError,
    RateDateInFutureError,
    RateNotFoundError,
    RateRangeInvalidError,
    RatesUnavailableError,
)
from rinde.rates.domain.quote import ALL_KINDS, Market, Quote, QuoteKind, pair_of
from rinde.shared.domain.calendar import argentine_day
from rinde.shared.domain.money import Currency, Money
from rinde.shared.domain.rate_type import ALL_RATE_TYPES, RateType

_ORDER = {kind: index for index, kind in enumerate(ALL_KINDS)}


@dataclass(frozen=True, slots=True)
class RatesDependencies:
    quotes: QuoteRepository
    provider: RateProvider
    history: RateHistoryProvider
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
        self, day: date | None = None, types: frozenset[QuoteKind] = ALL_RATE_TYPES
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
        fetched: dict[QuoteKind, Quote] = {}
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


def kinds_for(source: Currency, target: Currency, rate_type: RateType) -> tuple[QuoteKind, ...]:
    """Qué cotizaciones hacen falta, en orden, para llevar `source` a `target`.

    El tramo entre dólares y pesos usa el dólar elegido; el tramo entre Bitcoin
    y dólares, el precio del Bitcoin (ADR-0029).
    """
    bitcoin = pair_of(Market.BITCOIN)
    return tuple(Market.BITCOIN if pair == bitcoin else rate_type for pair in route(source, target))


class ConvertAmount:
    """Un monto en otra moneda, con el dólar elegido y las cotizaciones del día (ADR-0017).

    Se convierte al consultar, con el histórico guardado: el mismo día da
    siempre el mismo resultado, porque una fila guardada no cambia. Bitcoin a
    pesos son dos pasos, y la respuesta dice los dos (ADR-0029).
    """

    def __init__(self, deps: RatesDependencies) -> None:
        self._quotes = GetQuotes(deps)

    async def execute(
        self, money: Money, target: Currency, rate_type: RateType, day: date | None = None
    ) -> Conversion:
        if money.currency is target:
            raise ConversionSameCurrencyError
        kinds = kinds_for(money.currency, target, rate_type)
        found = {
            quote.rate_type: quote for quote in await self._quotes.execute(day, frozenset(kinds))
        }
        if any(kind not in found for kind in kinds):
            raise RateNotFoundError
        return convert(money, *(found[kind] for kind in kinds))


# Un día sin cotización propia (un feriado que la fuente no completó) toma la
# del último día anterior que la tenga: sin operaciones, vale el último precio.
# Es lo mismo que hace la fuente con los fines de semana. Más allá de este tope
# ya no es el precio de ese día, y el dato falta: no se inventa (ADR-0018).
MAX_CARRY_FORWARD = timedelta(days=6)
# Dos años y algo: lo que muestra el dashboard como máximo. Acota la consulta y
# la memoria de un pedido.
MAX_RANGE = timedelta(days=800)
_ONE_DAY = timedelta(days=1)


class GetQuoteSeries:
    """Un tipo de dólar, o un mercado, para cada día de un rango (ADR-0018, ADR-0029).

    * Los días cerrados salen de la base. Si falta alguno, se trae la serie
      completa de la fuente en un solo pedido y se guarda lo que faltaba.
    * Hoy sale de las fuentes, como en `GetQuotes`, y no se guarda.
    * Si una fuente no responde, sirve lo guardado: el día que no se pudo
      completar queda afuera del resultado, y quien lo usa lo informa.
    """

    def __init__(self, deps: RatesDependencies) -> None:
        self._deps = deps
        self._quotes = GetQuotes(deps)

    async def execute(self, rate_type: QuoteKind, since: date, until: date) -> dict[date, Quote]:
        now = self._deps.clock.now()
        today = argentine_day(now)
        if since > until or until - since > MAX_RANGE:
            raise RateRangeInvalidError
        if until > today:
            raise RateDateInFutureError

        lookback = since - MAX_CARRY_FORWARD
        closed_until = min(until, today - _ONE_DAY)
        by_day: dict[date, Quote] = {}
        if lookback <= closed_until:
            stored = await self._deps.quotes.for_range(rate_type, lookback, closed_until)
            by_day = {quote.day: quote for quote in stored}
            if len(_fill(by_day, since, closed_until)) < (closed_until - since).days + 1:
                by_day |= await self._load(rate_type, now, by_day, lookback, closed_until)
        if until == today:
            by_day |= await self._current(rate_type)
        return _fill(by_day, since, until)

    async def _load(
        self,
        rate_type: QuoteKind,
        now: datetime,
        stored: dict[date, Quote],
        since: date,
        until: date,
    ) -> dict[date, Quote]:
        try:
            series = await self._deps.history.series(rate_type)
        except RateSourceUnavailableError:
            return {}
        # Solo días cerrados del rango, del tipo pedido y que no estaban: una
        # fila guardada no se pisa, y hoy todavía se mueve.
        missing = {
            quote.day: quote
            for quote in series
            if quote.rate_type is rate_type
            and since <= quote.day <= until
            and quote.day not in stored
        }
        if missing:
            await self._deps.quotes.add_all(missing.values(), now)
            await self._deps.transaction.commit()
        return missing

    async def _current(self, rate_type: QuoteKind) -> dict[date, Quote]:
        try:
            quotes = await self._quotes.execute(None, frozenset({rate_type}))
        except RatesUnavailableError:
            return {}
        return {quote.day: quote for quote in quotes}


def _fill(by_day: dict[date, Quote], since: date, until: date) -> dict[date, Quote]:
    """Cada día con su cotización o, si no tiene, con la última anterior dentro del tope.

    La cotización arrastrada conserva su fecha: quien la mira sabe de qué día es.
    """
    result: dict[date, Quote] = {}
    last: Quote | None = None
    day = since - MAX_CARRY_FORWARD
    while day <= until:
        last = by_day.get(day, last)
        if last is not None and day - last.day > MAX_CARRY_FORWARD:
            last = None
        if day >= since and last is not None:
            result[day] = last
        day += _ONE_DAY
    return result
