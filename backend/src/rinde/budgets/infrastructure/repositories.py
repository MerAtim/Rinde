"""Repositorio de presupuestos sobre PostgreSQL. No confirma: lo hace la transacción.

Solo agrega y lee: no hay forma de cambiar ni de borrar una vigencia (ADR-0021).
"""

from datetime import date
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rinde.budgets.domain.budget import BudgetLimit
from rinde.budgets.domain.errors import BudgetCategoryNotFoundError
from rinde.budgets.infrastructure.tables import budget_limits
from rinde.shared.domain.money import Currency, Money

FOREIGN_KEY_VIOLATION = "23503"


class SqlAlchemyBudgetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, limit: BudgetLimit) -> None:
        try:
            # Un punto de guardado: si la fila falla, la sesión sigue usable.
            async with self._session.begin_nested():
                await self._session.execute(
                    insert(budget_limits).values(
                        id=limit.id,
                        owner_id=limit.owner_id,
                        category_id=limit.category_id,
                        since=limit.since,
                        amount=None if limit.limit is None else limit.limit.amount,
                        currency=None if limit.limit is None else limit.limit.currency.value,
                        recorded_at=limit.recorded_at,
                    )
                )
        except IntegrityError as error:
            # La categoría se borró entre la validación y la escritura.
            if getattr(error.orig, "sqlstate", None) == FOREIGN_KEY_VIOLATION:
                raise BudgetCategoryNotFoundError from error
            raise

    async def history(self, owner_id: UUID, until: date) -> list[BudgetLimit]:
        result = await self._session.execute(
            select(budget_limits)
            .where(budget_limits.c.owner_id == owner_id, budget_limits.c.since <= until)
            .order_by(budget_limits.c.since, budget_limits.c.recorded_at)
        )
        return [
            BudgetLimit(
                id=row["id"],
                owner_id=row["owner_id"],
                category_id=row["category_id"],
                since=row["since"],
                limit=None
                if row["amount"] is None
                else Money(row["amount"], Currency(row["currency"])),
                recorded_at=row["recorded_at"],
            )
            for row in result.mappings()
        ]
