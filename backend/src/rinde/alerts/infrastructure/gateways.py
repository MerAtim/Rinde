"""Adaptadores hacia los otros módulos: alertas los lee por su capa de aplicación.

Cada adaptador abre su propia unidad de trabajo y la cierra al terminar.
"""

from uuid import UUID

from rinde.alerts.application.ports import BudgetReading, CategoryInfo, MonthReading
from rinde.alerts.domain.alert import Threshold
from rinde.budgets.application.unit import BudgetsUnitFactory
from rinde.transactions.application.unit import TransactionsUnitFactory

# El estado se compara por su valor: el dominio de presupuestos no se importa directo.
# Los umbrales son los suyos (ADR-0021); "on_track" no llegó a ninguno.
_REACHED = {"warning": Threshold.WARNING, "over": Threshold.OVER}


class BudgetsMonthReader:
    def __init__(self, factory: BudgetsUnitFactory) -> None:
        self._factory = factory

    async def current_month(self, owner_id: UUID) -> MonthReading:
        async with self._factory() as unit:
            result = await unit.get.execute(owner_id)
        return MonthReading(
            month=result.month,
            budgets=[
                BudgetReading(
                    category_id=item.category.id,
                    limit=item.progress.limit,
                    spent=item.progress.spent,
                    reached=_REACHED.get(item.progress.status.value),
                )
                for item in result.items
            ],
        )


class TransactionsCategoryReader:
    def __init__(self, factory: TransactionsUnitFactory) -> None:
        self._factory = factory

    async def categories(self, owner_id: UUID) -> list[CategoryInfo]:
        async with self._factory() as unit:
            categories = await unit.categories.execute(owner_id)
        return [
            CategoryInfo(id=category.id, name=category.name.value, slug=category.slug)
            for category in categories
        ]
