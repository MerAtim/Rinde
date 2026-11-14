"""Unidad de trabajo de inflación: los casos de uso de un pedido, con una transacción."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from rinde.inflation.application.use_cases import GetCpi, InflationDependencies


@dataclass(frozen=True, slots=True)
class InflationUnit:
    cpi: GetCpi


class InflationUnitFactory(Protocol):
    """La raíz de composición elige la implementación: base real o memoria en tests."""

    def __call__(self) -> AbstractAsyncContextManager[InflationUnit]: ...


def build_inflation_unit(deps: InflationDependencies) -> InflationUnit:
    return InflationUnit(cpi=GetCpi(deps))
