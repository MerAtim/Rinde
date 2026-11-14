"""Repositorio del IPC sobre PostgreSQL. No confirma: lo hace la transacción."""

from collections.abc import Iterable
from datetime import date, datetime

from sqlalchemy import RowMapping, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rinde.inflation.domain.cpi import CpiMonth, CpiSource
from rinde.inflation.infrastructure.tables import cpi_months


def _to_month(row: RowMapping) -> CpiMonth:
    return CpiMonth(month=row["month"], index=row["value"], source=CpiSource(row["source"]))


class SqlAlchemyCpiRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def for_range(self, since: date, until: date) -> list[CpiMonth]:
        result = await self._session.execute(
            select(cpi_months)
            .where(cpi_months.c.month.between(since, until))
            .order_by(cpi_months.c.month)
        )
        return [_to_month(row) for row in result.mappings()]

    async def latest(self) -> CpiMonth | None:
        result = await self._session.execute(
            select(cpi_months).order_by(cpi_months.c.month.desc()).limit(1)
        )
        row = result.mappings().first()
        return None if row is None else _to_month(row)

    async def add_all(self, months: Iterable[CpiMonth], fetched_at: datetime) -> None:
        rows = [
            {
                "month": cpi.month,
                "value": cpi.index,
                "source": cpi.source.value,
                "fetched_at": fetched_at,
            }
            for cpi in months
        ]
        if not rows:
            return
        # Dos pedidos pueden traer el mismo mes a la vez: el segundo no falla ni pisa.
        await self._session.execute(insert(cpi_months).values(rows).on_conflict_do_nothing())
