"""El IPC del INDEC desde la API de series de tiempo del Estado (ADR-0025).

La respuesta trae `data` como pares `[fecha, valor]`, un par por mes. Cada par
se valida por separado y uno inválido se descarta solo: el resto de la serie
sigue sirviendo. Un cuerpo con otra forma cuenta como fuente caída.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Annotated

import httpx
from pydantic import BaseModel, ConfigDict, Strict, ValidationError

from rinde.inflation.application.ports import CpiSourceUnavailableError
from rinde.inflation.domain.cpi import CpiMonth, CpiSource, round_index
from rinde.inflation.domain.errors import CpiMonthInvalidError
from rinde.shared.infrastructure.http import SourceUnavailableError, get_json

logger = logging.getLogger(__name__)

SERIES_ID = "148.3_INIVELNAL_DICI_M_26"
"""IPC nacional, nivel general, base diciembre de 2016, mensual."""
TIMEOUT_SECONDS = 3.0
# La API corta en 1000 valores por pedido: son más de 80 años de meses.
LIMIT = 1000

# Solo `Decimal`: el JSON se lee con los números como `Decimal`, así que un
# string, un booleano o un `null` en ese lugar es un dato que no sirve.
_Index = Annotated[Decimal, Strict()]


class _Point(BaseModel):
    model_config = ConfigDict(frozen=True)

    month: date
    index: _Index


class _Body(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    data: list[object]


class DatosGobArCpiProvider:
    def __init__(self, client: httpx.AsyncClient, *, base_url: str) -> None:
        self._client = client
        self._url = str(
            httpx.URL(
                f"{base_url.rstrip('/')}/series/api/series/",
                params={"ids": SERIES_ID, "format": "json", "limit": LIMIT, "sort": "asc"},
            )
        )

    async def series(self) -> list[CpiMonth]:
        try:
            body = await get_json(self._client, self._url, timeout_seconds=TIMEOUT_SECONDS)
            parsed = _Body.model_validate(body)
        except SourceUnavailableError, ValidationError:
            raise CpiSourceUnavailableError(self._url) from None
        found: dict[date, CpiMonth] = {}
        for raw in parsed.data:
            cpi = _month(raw)
            # Si la fuente repite un mes, vale el primero: nunca se pisa un dato.
            if cpi is not None:
                found.setdefault(cpi.month, cpi)
        return sorted(found.values(), key=lambda cpi: cpi.month)


def _month(raw: object) -> CpiMonth | None:
    if not isinstance(raw, list) or len(raw) != 2:  # noqa: PLR2004  (un par fecha y valor)
        return None
    try:
        point = _Point.model_validate({"month": raw[0], "index": raw[1]})
        return CpiMonth(point.month, round_index(point.index), CpiSource.INDEC)
    except ValidationError, CpiMonthInvalidError:
        logger.warning("Mes del IPC inválido: se descarta")
        return None
