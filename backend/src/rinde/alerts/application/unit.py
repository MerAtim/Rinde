"""Unidad de trabajo de alertas: los casos de uso de un pedido, con una transacción."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from rinde.alerts.application.ports import (
    AlertRepository,
    BudgetReader,
    CategoryReader,
    Clock,
    Transaction,
)
from rinde.alerts.application.use_cases import (
    AlertsDependencies,
    EvaluateBudgetAlerts,
    ListAlerts,
    MarkAlertsRead,
)


@dataclass(frozen=True, slots=True)
class AlertsGateways:
    """Lo que alertas lee de los otros módulos. Cada uno abre su propia unidad."""

    budgets: BudgetReader
    categories: CategoryReader


@dataclass(frozen=True, slots=True)
class AlertsUnit:
    evaluate: EvaluateBudgetAlerts
    list: ListAlerts
    mark_read: MarkAlertsRead


class AlertsUnitFactory(Protocol):
    """La raíz de composición elige la implementación: base real o memoria en tests."""

    def __call__(self) -> AbstractAsyncContextManager[AlertsUnit]: ...


def build_alerts_unit(
    alerts: AlertRepository,
    transaction: Transaction,
    gateways: AlertsGateways,
    clock: Clock,
) -> AlertsUnit:
    deps = AlertsDependencies(
        alerts=alerts,
        transaction=transaction,
        budgets=gateways.budgets,
        categories=gateways.categories,
        clock=clock,
    )
    return AlertsUnit(
        evaluate=EvaluateBudgetAlerts(deps),
        list=ListAlerts(deps),
        mark_read=MarkAlertsRead(deps),
    )
