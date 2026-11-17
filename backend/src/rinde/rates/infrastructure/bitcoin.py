"""Fuentes del precio del Bitcoin en dólares: Kraken y Bitstamp (ADR-0029).

Las dos son exchanges que publican sin clave la compra y la venta de hoy y una
vela por día. Los precios llegan como texto; se aceptan solo si son un número
decimal positivo, sin exponente: la respuesta de un tercero es una entrada no
confiable como cualquier otra.

Una vela diaria empieza a las 00:00 UTC de su día y cierra a las 21 de
Argentina del mismo día: su cierre es el precio de ese día, como compra y como
venta, porque el histórico no informa las dos puntas. La vela del día en curso
también llega; el caso de uso guarda solo días cerrados.
"""

import logging
import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
from pydantic import BaseModel, ConfigDict, StrictStr, ValidationError

from rinde.rates.application.ports import Clock, QuoteRequest, RateSourceUnavailableError
from rinde.rates.domain.errors import QuoteInvalidError
from rinde.rates.domain.quote import Market, Quote, QuoteKind, RateSource, pair_of, round_rate
from rinde.rates.infrastructure.http import get_json
from rinde.rates.infrastructure.sources import (
    SERIES_MAX_BYTES,
    SERIES_TIMEOUT_SECONDS,
    TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

# Un precio "de hoy" que el exchange actualizó hace más de esto no es de hoy:
# el Bitcoin opera todo el día, todos los días.
MAX_CURRENT_AGE = timedelta(hours=1)

_PRICE = re.compile(r"\d{1,16}(\.\d{1,12})?")


def _price(raw: str) -> Decimal:
    if not _PRICE.fullmatch(raw):
        raise ValueError(raw)
    return Decimal(raw)


def _day_of(timestamp: int) -> date:
    return datetime.fromtimestamp(timestamp, UTC).date()


def _quote(
    day: date, buy: Decimal, sell: Decimal, source: RateSource, updated_at: datetime | None
) -> Quote | None:
    base, counter = pair_of(Market.BITCOIN)
    try:
        return Quote(
            rate_type=Market.BITCOIN,
            day=day,
            buy=round_rate(buy),
            sell=round_rate(sell),
            source=source,
            updated_at=updated_at,
            base=base,
            counter=counter,
        )
    except QuoteInvalidError:
        logger.warning("Precio del Bitcoin inválido de %s: se descarta", source)
        return None


def _wants_today(request: QuoteRequest) -> bool:
    return request.current and Market.BITCOIN in request.types


class _KrakenTicker(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    # [precio, volumen entero del lote, volumen del lote]: solo importa el precio.
    a: list[StrictStr]
    b: list[StrictStr]


class _KrakenAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    error: list[StrictStr]
    result: dict[str, object]


class KrakenProvider:
    """api.kraken.com: compra y venta de hoy, y unas 720 velas diarias."""

    _PAIR = "XBTUSD"
    # Kraken nombra el par a su manera en la respuesta.
    _KEY = "XXBTZUSD"

    def __init__(self, client: httpx.AsyncClient, *, base_url: str) -> None:
        self._client = client
        self._base_url = f"{base_url.rstrip('/')}/0/public"

    async def quotes(self, request: QuoteRequest) -> dict[QuoteKind, Quote]:
        if not _wants_today(request):
            return {}
        url = f"{self._base_url}/Ticker?pair={self._PAIR}"
        try:
            ticker = _KrakenTicker.model_validate(await self._result(url))
            # Compra: lo que paga quien compra (bid). Venta: lo que pide quien vende (ask).
            buy, sell = _price(ticker.b[0]), _price(ticker.a[0])
        except ValidationError, ValueError, IndexError:
            raise RateSourceUnavailableError(url) from None
        quote = _quote(request.day, buy, sell, RateSource.KRAKEN, None)
        return {} if quote is None else {Market.BITCOIN: quote}

    async def series(self, rate_type: QuoteKind) -> list[Quote]:
        if rate_type is not Market.BITCOIN:
            return []
        url = f"{self._base_url}/OHLC?pair={self._PAIR}&interval=1440"
        rows = await self._result(url, series=True)
        if not isinstance(rows, list):
            raise RateSourceUnavailableError(url)
        found: dict[date, Quote] = {}
        for row in rows:
            # Cada vela es una lista: el inicio en segundos primero, el cierre quinto.
            try:
                if not isinstance(row, list) or not isinstance(row[0], Decimal):
                    continue
                day, close = _day_of(int(row[0])), _price(row[4])
            except ValueError, IndexError, TypeError, OverflowError, OSError:
                continue
            quote = _quote(day, close, close, RateSource.KRAKEN, None)
            if quote is not None:
                found.setdefault(day, quote)
        return sorted(found.values(), key=lambda quote: quote.day)

    async def _result(self, url: str, *, series: bool = False) -> object:
        body = await get_json(
            self._client,
            url,
            timeout_seconds=SERIES_TIMEOUT_SECONDS if series else TIMEOUT_SECONDS,
            **({"max_bytes": SERIES_MAX_BYTES} if series else {}),
        )
        try:
            answer = _KrakenAnswer.model_validate(body)
        except ValidationError:
            raise RateSourceUnavailableError(url) from None
        # Kraken responde 200 con la lista de errores llena cuando algo falla.
        if answer.error or self._KEY not in answer.result:
            raise RateSourceUnavailableError(url)
        return answer.result[self._KEY]


class _BitstampTicker(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    bid: StrictStr
    ask: StrictStr
    timestamp: StrictStr


class _BitstampCandle(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    timestamp: StrictStr
    close: StrictStr


class _BitstampOhlc(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    ohlc: list[object]


class _BitstampSeries(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    data: _BitstampOhlc


class BitstampProvider:
    """www.bitstamp.net: compra y venta de hoy, y hasta 1000 velas diarias. Respaldo de Kraken."""

    _MAX_CANDLES = 1000

    def __init__(self, client: httpx.AsyncClient, clock: Clock, *, base_url: str) -> None:
        self._client = client
        self._clock = clock
        self._base_url = f"{base_url.rstrip('/')}/api/v2"

    async def quotes(self, request: QuoteRequest) -> dict[QuoteKind, Quote]:
        if not _wants_today(request):
            return {}
        url = f"{self._base_url}/ticker/btcusd/"
        body = await get_json(self._client, url, timeout_seconds=TIMEOUT_SECONDS)
        try:
            ticker = _BitstampTicker.model_validate(body)
            buy, sell = _price(ticker.bid), _price(ticker.ask)
            updated_at = datetime.fromtimestamp(int(ticker.timestamp), UTC)
        except ValidationError, ValueError, OverflowError, OSError:
            raise RateSourceUnavailableError(url) from None
        if self._clock.now() - updated_at > MAX_CURRENT_AGE:
            return {}
        quote = _quote(request.day, buy, sell, RateSource.BITSTAMP, updated_at)
        return {} if quote is None else {Market.BITCOIN: quote}

    async def series(self, rate_type: QuoteKind) -> list[Quote]:
        if rate_type is not Market.BITCOIN:
            return []
        url = f"{self._base_url}/ohlc/btcusd/?step=86400&limit={self._MAX_CANDLES}"
        body = await get_json(
            self._client, url, timeout_seconds=SERIES_TIMEOUT_SECONDS, max_bytes=SERIES_MAX_BYTES
        )
        try:
            candles = _BitstampSeries.model_validate(body).data.ohlc
        except ValidationError:
            raise RateSourceUnavailableError(url) from None
        found: dict[date, Quote] = {}
        for raw in candles:
            try:
                candle = _BitstampCandle.model_validate(raw)
                day, close = _day_of(int(candle.timestamp)), _price(candle.close)
            except ValidationError, ValueError, OverflowError, OSError:
                continue
            quote = _quote(day, close, close, RateSource.BITSTAMP, None)
            if quote is not None:
                found.setdefault(day, quote)
        return sorted(found.values(), key=lambda quote: quote.day)
