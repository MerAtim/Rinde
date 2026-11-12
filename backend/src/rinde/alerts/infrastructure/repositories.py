"""Repositorio de alertas sobre PostgreSQL. No confirma: lo hace la transacción."""

from collections import defaultdict
from collections.abc import Collection
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rinde.alerts.domain.alert import BudgetAlert, Threshold
from rinde.alerts.infrastructure.tables import ONCE_PER_MONTH, budget_alerts
from rinde.shared.domain.money import Currency, Money


class SqlAlchemyAlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, alert: BudgetAlert) -> bool:
        # Si otro pedido la guardó primero, no es un error: es la regla de "una vez".
        # RETURNING dice si la fila entró, sin depender del conteo del driver.
        inserted = await self._session.scalar(
            insert(budget_alerts)
            .values(
                id=alert.id,
                owner_id=alert.owner_id,
                category_id=alert.category_id,
                month=alert.month,
                threshold=alert.threshold.value,
                limit_amount=alert.limit.amount,
                spent_amount=alert.spent.amount,
                currency=alert.limit.currency.value,
                raised_at=alert.raised_at,
                read_at=alert.read_at,
            )
            .on_conflict_do_nothing(index_elements=list(ONCE_PER_MONTH))
            .returning(budget_alerts.c.id)
        )
        return inserted is not None

    async def raised_in(self, owner_id: UUID, month: date) -> dict[UUID, set[Threshold]]:
        result = await self._session.execute(
            select(budget_alerts.c.category_id, budget_alerts.c.threshold).where(
                budget_alerts.c.owner_id == owner_id, budget_alerts.c.month == month
            )
        )
        raised: defaultdict[UUID, set[Threshold]] = defaultdict(set)
        for category_id, threshold in result.tuples():
            raised[category_id].add(Threshold(threshold))
        return dict(raised)

    async def latest(self, owner_id: UUID, limit: int) -> list[BudgetAlert]:
        result = await self._session.execute(
            select(budget_alerts)
            .where(budget_alerts.c.owner_id == owner_id)
            # El id desempata dos alertas del mismo instante: el orden no cambia entre pedidos.
            .order_by(budget_alerts.c.raised_at.desc(), budget_alerts.c.id.desc())
            .limit(limit)
        )
        return [
            BudgetAlert(
                id=row["id"],
                owner_id=row["owner_id"],
                category_id=row["category_id"],
                month=row["month"],
                threshold=Threshold(row["threshold"]),
                limit=Money(row["limit_amount"], Currency(row["currency"])),
                spent=Money(row["spent_amount"], Currency(row["currency"])),
                raised_at=row["raised_at"],
                read_at=row["read_at"],
            )
            for row in result.mappings()
        ]

    async def unread_count(self, owner_id: UUID) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(budget_alerts)
            .where(budget_alerts.c.owner_id == owner_id, budget_alerts.c.read_at.is_(None))
        )
        return count or 0

    async def mark_read(self, owner_id: UUID, ids: Collection[UUID], at: datetime) -> None:
        await self._session.execute(
            update(budget_alerts)
            .where(
                budget_alerts.c.owner_id == owner_id,
                budget_alerts.c.id.in_(list(ids)),
                budget_alerts.c.read_at.is_(None),
            )
            .values(read_at=at)
        )
