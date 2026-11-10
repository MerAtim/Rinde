"""Unidad de trabajo de cotizaciones: los casos de uso de un pedido, con una transacción."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from rinde.rates.application.use_cases import GetQuote, GetQuotes, RatesDependencies


@dataclass(frozen=True, slots=True)
class RatesUnit:
    list: GetQuotes
    get: GetQuote


class RatesUnitFactory(Protocol):
    """La raíz de composición elige la implementación: base real o memoria en tests."""

    def __call__(self) -> AbstractAsyncContextManager[RatesUnit]: ...


def build_rates_unit(deps: RatesDependencies) -> RatesUnit:
    return RatesUnit(list=GetQuotes(deps), get=GetQuote(deps))
