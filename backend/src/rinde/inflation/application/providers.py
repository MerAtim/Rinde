"""Caché de la serie del IPC (ADR-0025)."""

import asyncio
from datetime import datetime, timedelta

from rinde.inflation.application.ports import Clock, CpiProvider
from rinde.inflation.domain.cpi import CpiMonth


class CachedCpiProvider:
    """Decorador: la última serie, en memoria durante un rato.

    Del 1 al 15 de cada mes el mes pasado todavía no está publicado: sin esto,
    cada pedido de pesos constantes iría a la fuente a buscarlo. Un error no se
    guarda, así que el pedido siguiente vuelve a probar.

    Un candado: mientras un pedido consulta la fuente, los demás esperan y
    después leen lo que trajo.
    """

    def __init__(self, inner: CpiProvider, clock: Clock, *, ttl: timedelta) -> None:
        self._inner = inner
        self._clock = clock
        self._ttl = ttl
        self._entry: tuple[datetime, list[CpiMonth]] | None = None
        self._lock = asyncio.Lock()

    async def series(self) -> list[CpiMonth]:
        async with self._lock:
            now = self._clock.now()
            if self._entry is not None and self._entry[0] > now:
                return self._entry[1]
            series = await self._inner.series()
            self._entry = (now + self._ttl, series)
            return series
