"""Unidad de trabajo de presupuestos: los casos de uso de un pedido, con una transacción."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from rinde.budgets.application.ports import (
    BudgetRepository,
    CategoryReader,
    Clock,
    ConverterFactory,
    RateTypeReader,
    SpendingReader,
    Transaction,
)
from rinde.budgets.application.use_cases import (
    BudgetsDependencies,
    GetBudgets,
    RemoveBudget,
    SetBudget,
)


@dataclass(frozen=True, slots=True)
class BudgetsGateways:
    """Lo que presupuestos lee de los otros módulos. Cada uno abre su propia unidad."""

    categories: CategoryReader
    spending: SpendingReader
    rate_types: RateTypeReader
    converters: ConverterFactory


@dataclass(frozen=True, slots=True)
class BudgetsUnit:
    get: GetBudgets
    set: SetBudget
    remove: RemoveBudget


class BudgetsUnitFactory(Protocol):
    """La raíz de composición elige la implementación: base real o memoria en tests."""

    def __call__(self) -> AbstractAsyncContextManager[BudgetsUnit]: ...


def build_budgets_unit(
    budgets: BudgetRepository,
    transaction: Transaction,
    gateways: BudgetsGateways,
    clock: Clock,
) -> BudgetsUnit:
    deps = BudgetsDependencies(
        budgets=budgets,
        transaction=transaction,
        categories=gateways.categories,
        spending=gateways.spending,
        rate_types=gateways.rate_types,
        converters=gateways.converters,
        clock=clock,
    )
    return BudgetsUnit(get=GetBudgets(deps), set=SetBudget(deps), remove=RemoveBudget(deps))
