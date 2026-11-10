"""Fuentes y repositorio de cotizaciones en memoria."""

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal

from rinde.rates.application.ports import QuoteRequest, RateSourceUnavailableError
from rinde.rates.domain.quote import Quote, RateSource, RateType


def quote(
    rate_type: RateType = RateType.MEP,
    day: date = date(2026, 11, 10),
    *,
    buy: str = "1560.2",
    sell: str = "1587.9",
    source: RateSource = RateSource.DOLARAPI,
) -> Quote:
    return Quote(rate_type=rate_type, day=day, buy=Decimal(buy), sell=Decimal(sell), source=source)


class FakeRateProvider:
    """Responde lo que tiene cargado, o falla si está caída. Anota cada pedido."""

    def __init__(self, *quotes: Quote, down: bool = False) -> None:
        self.stock = list(quotes)
        self.down = down
        self.requests: list[QuoteRequest] = []

    async def quotes(self, request: QuoteRequest) -> dict[RateType, Quote]:
        self.requests.append(request)
        if self.down:
            raise RateSourceUnavailableError
        return {
            q.rate_type: q
            for q in self.stock
            if q.day == request.day and q.rate_type in request.types
        }


class InMemoryQuotes:
    def __init__(self, *quotes: Quote) -> None:
        self.rows: dict[tuple[date, RateType, RateSource], Quote] = {}
        self.fetched_at: dict[tuple[date, RateType, RateSource], datetime] = {}
        for item in quotes:
            self.rows[(item.day, item.rate_type, item.source)] = item

    async def for_day(self, day: date, types: frozenset[RateType]) -> list[Quote]:
        found: dict[RateType, Quote] = {}
        for (row_day, rate_type, _), item in sorted(self.rows.items()):
            if row_day == day and rate_type in types:
                found.setdefault(rate_type, item)
        return list(found.values())

    async def add_all(self, quotes: Iterable[Quote], fetched_at: datetime) -> None:
        for item in quotes:
            key = (item.day, item.rate_type, item.source)
            if key not in self.rows:
                self.rows[key] = item
                self.fetched_at[key] = fetched_at
