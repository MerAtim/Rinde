"""Adaptadores de las fuentes de cotizaciones (ADR-0016).

Cada fuente nombra los dólares a su manera. Cada adaptador traduce solo los
tipos que esa fuente publica con la misma definición que usa Rinde: si no es el
mismo dólar, no se traduce, aunque se llame parecido. El "oficial" del BCRA es
el mayorista, no el de Banco Nación, y el MEP de CriptoYa es un precio por bono,
sin compra ni venta; por eso esos no están.

Un elemento inválido se descarta solo: el resto de la respuesta sigue sirviendo,
y el tipo que falta se le pide a la fuente siguiente.
"""

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, ClassVar

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Strict, ValidationError

from rinde.rates.application.ports import Clock, QuoteRequest, RateSourceUnavailableError
from rinde.rates.domain.errors import QuoteInvalidError
from rinde.rates.domain.quote import Quote, RateSource, RateType, round_rate
from rinde.rates.infrastructure.http import get_json

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 3.0
# Un valor "de hoy" que la fuente actualizó hace más de esto no es de hoy: la
# fuente se trabó. Alcanza para un fin de semana largo con feriados puente.
MAX_CURRENT_AGE = timedelta(days=6)

# DolarAPI y ArgentinaDatos usan los mismos nombres.
_CASAS: dict[str, RateType] = {
    "oficial": RateType.OFFICIAL,
    "bolsa": RateType.MEP,
    "contadoconliqui": RateType.CCL,
    "blue": RateType.BLUE,
    "tarjeta": RateType.CARD,
    "cripto": RateType.CRYPTO,
}
_CASA_BY_TYPE = {rate_type: casa for casa, rate_type in _CASAS.items()}

# Solo `Decimal`: el JSON se lee con los números como `Decimal`, así que un
# string o un booleano en ese lugar es una respuesta con otra forma.
_Rate = Annotated[Decimal, Strict()]


class _Item(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    casa: str
    compra: _Rate
    venta: _Rate


class _DolarApiItem(_Item):
    fechaActualizacion: AwareDatetime  # noqa: N815  (el nombre lo pone la fuente)


class _ArgentinaDatosItem(_Item):
    fecha: date


class _CriptoYaItem(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    bid: _Rate
    ask: _Rate
    timestamp: Decimal


def _build(
    rate_type: RateType,
    *,
    day: date,
    prices: tuple[Decimal, Decimal],
    source: RateSource,
    updated_at: datetime | None,
) -> Quote | None:
    try:
        return Quote(
            rate_type=rate_type,
            day=day,
            buy=round_rate(prices[0]),
            sell=round_rate(prices[1]),
            source=source,
            updated_at=updated_at,
        )
    except QuoteInvalidError:
        logger.warning("Cotización inválida de %s para %s: se descarta", source, rate_type)
        return None


def _is_stale(updated_at: datetime, now: datetime) -> bool:
    return now - updated_at > MAX_CURRENT_AGE


class DolarApiProvider:
    """dolarapi.com: todos los tipos, pero solo el último valor. No tiene histórico."""

    def __init__(self, client: httpx.AsyncClient, clock: Clock, *, base_url: str) -> None:
        self._client = client
        self._clock = clock
        self._url = f"{base_url.rstrip('/')}/v1/dolares"

    async def quotes(self, request: QuoteRequest) -> dict[RateType, Quote]:
        if not request.current:
            return {}
        body = await get_json(self._client, self._url, timeout_seconds=TIMEOUT_SECONDS)
        if not isinstance(body, list):
            raise RateSourceUnavailableError(self._url)
        now = self._clock.now()
        found: dict[RateType, Quote] = {}
        for raw in body:
            try:
                item = _DolarApiItem.model_validate(raw)
            except ValidationError:
                continue
            rate_type = _CASAS.get(item.casa)
            if rate_type not in request.types or _is_stale(item.fechaActualizacion, now):
                continue
            quote = _build(
                rate_type,
                day=request.day,
                prices=(item.compra, item.venta),
                source=RateSource.DOLARAPI,
                updated_at=item.fechaActualizacion.astimezone(UTC),
            )
            if quote is not None:
                found[rate_type] = quote
        return found


class ArgentinaDatosProvider:
    """api.argentinadatos.com: todos los tipos, día por día desde 2011.

    Es la única fuente de días pasados. Los fines de semana y feriados repite
    el último valor hábil, y no informa la hora: `updated_at` queda vacío.
    """

    def __init__(self, client: httpx.AsyncClient, *, base_url: str) -> None:
        self._client = client
        self._base_url = f"{base_url.rstrip('/')}/v1/cotizaciones/dolares"

    async def quotes(self, request: QuoteRequest) -> dict[RateType, Quote]:
        types = sorted(request.types)
        results = await asyncio.gather(
            *(self._one(rate_type, request.day) for rate_type in types), return_exceptions=True
        )
        found: dict[RateType, Quote] = {}
        failures = 0
        for rate_type, result in zip(types, results, strict=True):
            if isinstance(result, RateSourceUnavailableError):
                failures += 1
            elif isinstance(result, BaseException):
                raise result
            elif result is not None:
                found[rate_type] = result
        # Si no respondió ningún pedido, la fuente está caída; si respondió alguno, no.
        if types and failures == len(types):
            raise RateSourceUnavailableError(self._base_url)
        return found

    async def _one(self, rate_type: RateType, day: date) -> Quote | None:
        url = f"{self._base_url}/{_CASA_BY_TYPE[rate_type]}/{day:%Y/%m/%d}"
        body = await get_json(self._client, url, timeout_seconds=TIMEOUT_SECONDS)
        if body is None:
            return None
        try:
            item = _ArgentinaDatosItem.model_validate(body)
        except ValidationError:
            raise RateSourceUnavailableError(url) from None
        if item.fecha != day or _CASAS.get(item.casa) is not rate_type:
            raise RateSourceUnavailableError(url)
        return _build(
            rate_type,
            day=day,
            prices=(item.compra, item.venta),
            source=RateSource.ARGENTINADATOS,
            updated_at=None,
        )


class CriptoYaProvider:
    """criptoya.com: solo el último valor, y solo oficial y blue con compra y venta.

    Es la fuente independiente de las otras dos, que son del mismo autor y se
    pueden caer juntas.
    """

    _KEYS: ClassVar[dict[str, RateType]] = {"oficial": RateType.OFFICIAL, "blue": RateType.BLUE}

    def __init__(self, client: httpx.AsyncClient, clock: Clock, *, base_url: str) -> None:
        self._client = client
        self._clock = clock
        self._url = f"{base_url.rstrip('/')}/api/dolar"

    async def quotes(self, request: QuoteRequest) -> dict[RateType, Quote]:
        wanted = {key: t for key, t in self._KEYS.items() if t in request.types}
        if not request.current or not wanted:
            return {}
        body = await get_json(self._client, self._url, timeout_seconds=TIMEOUT_SECONDS)
        if not isinstance(body, dict):
            raise RateSourceUnavailableError(self._url)
        now = self._clock.now()
        found: dict[RateType, Quote] = {}
        for key, rate_type in wanted.items():
            try:
                item = _CriptoYaItem.model_validate(body.get(key))
                updated_at = datetime.fromtimestamp(int(item.timestamp), UTC)
            except ValidationError, ValueError, OverflowError, OSError:
                continue
            if _is_stale(updated_at, now):
                continue
            quote = _build(
                rate_type,
                day=request.day,
                prices=(item.bid, item.ask),
                source=RateSource.CRIPTOYA,
                updated_at=updated_at,
            )
            if quote is not None:
                found[rate_type] = quote
        return found
