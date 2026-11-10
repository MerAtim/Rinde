"""Repositorio de cotizaciones sobre PostgreSQL. No confirma: lo hace la transacción."""

from collections.abc import Iterable
from datetime import date, datetime

from sqlalchemy import RowMapping, case, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rinde.rates.domain.quote import Quote, RateSource, RateType
from rinde.rates.infrastructure.tables import exchange_rates
from rinde.shared.domain.money import Currency

# Si un día quedó guardado de más de una fuente, gana la de mayor prioridad:
# la misma que en la cadena de fuentes.
_PRIORITY = case(
    {source.value: index for index, source in enumerate(RateSource)},
    value=exchange_rates.c.source,
)


def _to_quote(row: RowMapping) -> Quote:
    return Quote(
        rate_type=RateType(row["rate_type"]),
        day=row["day"],
        buy=row["buy"],
        sell=row["sell"],
        source=RateSource(row["source"]),
        updated_at=row["updated_at"],
        base=Currency(row["base"]),
        counter=Currency(row["counter"]),
    )


class SqlAlchemyQuoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def for_day(self, day: date, types: frozenset[RateType]) -> list[Quote]:
        if not types:
            return []
        result = await self._session.execute(
            select(exchange_rates)
            .where(
                exchange_rates.c.day == day,
                exchange_rates.c.base == Currency.USD.value,
                exchange_rates.c.counter == Currency.ARS.value,
                exchange_rates.c.rate_type.in_([t.value for t in types]),
            )
            .order_by(exchange_rates.c.rate_type, _PRIORITY)
            .distinct(exchange_rates.c.rate_type)
        )
        return [_to_quote(row) for row in result.mappings()]

    async def add_all(self, quotes: Iterable[Quote], fetched_at: datetime) -> None:
        rows = [
            {
                "day": quote.day,
                "base": quote.base.value,
                "counter": quote.counter.value,
                "rate_type": quote.rate_type.value,
                "source": quote.source.value,
                "buy": quote.buy,
                "sell": quote.sell,
                "updated_at": quote.updated_at,
                "fetched_at": fetched_at,
            }
            for quote in quotes
        ]
        if not rows:
            return
        # Dos pedidos del mismo día pueden traer lo mismo a la vez: el segundo no falla.
        await self._session.execute(insert(exchange_rates).values(rows).on_conflict_do_nothing())
