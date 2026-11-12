"""Lo que alertas escucha de otros módulos. La raíz de composición lo suscribe al bus."""

from rinde.alerts.application.unit import AlertsUnitFactory
from rinde.transactions.application.events import ExpenseRecorded


class EvaluateOnExpense:
    """Cada gasto registrado, editado o restaurado evalúa las alertas de su dueño (ADR-0022).

    El dueño es el del gasto: la evaluación nunca mira datos de otra persona.
    """

    def __init__(self, factory: AlertsUnitFactory) -> None:
        self._factory = factory

    async def __call__(self, event: ExpenseRecorded) -> None:
        async with self._factory() as unit:
            await unit.evaluate.execute(event.owner_id, event.occurred_on)
