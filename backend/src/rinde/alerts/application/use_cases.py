"""Casos de uso de alertas. Todos reciben el dueño: es el filtro de autorización."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from rinde.alerts.application.ports import (
    AlertRepository,
    BudgetReader,
    CategoryInfo,
    CategoryReader,
    Clock,
    Transaction,
)
from rinde.alerts.domain.alert import BudgetAlert, due_threshold
from rinde.shared.domain.calendar import argentine_day

FEED_SIZE = 50
"""Las alertas que se muestran. Son a lo sumo dos por categoría y por mes."""


@dataclass(frozen=True, slots=True)
class AlertsDependencies:
    alerts: AlertRepository
    transaction: Transaction
    budgets: BudgetReader
    categories: CategoryReader
    clock: Clock


class EvaluateBudgetAlerts:
    """Mide el mes en curso y guarda los umbrales que todavía no se avisaron.

    Mira el estado del mes entero, no cuánto cambió con el último gasto: evaluar
    dos veces da lo mismo que evaluar una, y una alerta que se perdió la levanta
    el próximo gasto del mes (ADR-0022).
    """

    def __init__(self, deps: AlertsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, day: date) -> list[BudgetAlert]:
        deps = self._deps
        now = deps.clock.now()
        # Una alerta sirve para frenar a tiempo: un mes cerrado no avisa.
        if day.replace(day=1) != argentine_day(now).replace(day=1):
            return []
        reading = await deps.budgets.current_month(owner_id)
        raised = await deps.alerts.raised_in(owner_id, reading.month)
        created: list[BudgetAlert] = []
        for budget in reading.budgets:
            threshold = due_threshold(budget.reached, raised.get(budget.category_id, set()))
            if threshold is None:
                continue
            alert = BudgetAlert(
                id=uuid4(),
                owner_id=owner_id,
                category_id=budget.category_id,
                month=reading.month,
                threshold=threshold,
                limit=budget.limit,
                spent=budget.spent,
                raised_at=now,
            )
            # Otro pedido pudo guardarla entre la lectura y la escritura.
            if await deps.alerts.add(alert):
                created.append(alert)
        if created:
            await deps.transaction.commit()
        return created


@dataclass(frozen=True, slots=True)
class AlertItem:
    alert: BudgetAlert
    category: CategoryInfo


@dataclass(frozen=True, slots=True)
class AlertFeed:
    unread: int
    """Todas las sin leer, aunque no entren en la lista."""
    items: list[AlertItem]


class ListAlerts:
    def __init__(self, deps: AlertsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID) -> AlertFeed:
        deps = self._deps
        alerts = await deps.alerts.latest(owner_id, FEED_SIZE)
        unread = await deps.alerts.unread_count(owner_id)
        if not alerts:
            return AlertFeed(unread, [])
        categories = {item.id: item for item in await deps.categories.categories(owner_id)}
        # Una categoría borrada se lleva sus alertas; si el borrado llegó mientras
        # se leía, la alerta huérfana no se muestra.
        items = [
            AlertItem(alert, categories[alert.category_id])
            for alert in alerts
            if alert.category_id in categories
        ]
        return AlertFeed(unread, items)


class MarkAlertsRead:
    """Marca las que la persona vio en la lista, no "todas": una nueva pudo llegar mientras."""

    def __init__(self, deps: AlertsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, ids: Collection[UUID]) -> None:
        if not ids:
            return
        deps = self._deps
        await deps.alerts.mark_read(owner_id, ids, deps.clock.now())
        await deps.transaction.commit()
