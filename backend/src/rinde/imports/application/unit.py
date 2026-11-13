"""Unidad de trabajo de importación: los casos de uso de un pedido, con una transacción."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from rinde.imports.application.ports import (
    AccountInspector,
    BatchRepository,
    CategoryReader,
    Clock,
    MovementRegistrar,
    Transaction,
)
from rinde.imports.application.use_cases import (
    ConfirmBatch,
    CreateBatch,
    DiscardBatch,
    GetBatch,
    ImportsDependencies,
)


@dataclass(frozen=True, slots=True)
class ImportsGateways:
    """Lo que importación usa de movimientos. Cada uno abre su propia unidad."""

    accounts: AccountInspector
    registrar: MovementRegistrar
    categories: CategoryReader


@dataclass(frozen=True, slots=True)
class ImportsUnit:
    create: CreateBatch
    get: GetBatch
    confirm: ConfirmBatch
    discard: DiscardBatch


class ImportsUnitFactory(Protocol):
    """La raíz de composición elige la implementación: base real o memoria en tests."""

    def __call__(self) -> AbstractAsyncContextManager[ImportsUnit]: ...


def build_imports_unit(
    batches: BatchRepository,
    transaction: Transaction,
    gateways: ImportsGateways,
    clock: Clock,
) -> ImportsUnit:
    deps = ImportsDependencies(
        batches=batches,
        transaction=transaction,
        accounts=gateways.accounts,
        registrar=gateways.registrar,
        categories=gateways.categories,
        clock=clock,
    )
    return ImportsUnit(
        create=CreateBatch(deps),
        get=GetBatch(deps),
        confirm=ConfirmBatch(deps),
        discard=DiscardBatch(deps),
    )
