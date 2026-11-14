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
    PdfText,
    RuleRepository,
    StatementReader,
    Transaction,
)
from rinde.imports.application.readers import MacroPdfReader
from rinde.imports.application.use_cases import (
    ConfirmBatch,
    CreateBatch,
    DiscardBatch,
    GetBatch,
    ImportsDependencies,
)


@dataclass(frozen=True, slots=True)
class ImportsGateways:
    """Lo que importación usa de afuera: movimientos, que abre su propia unidad, y el PDF."""

    accounts: AccountInspector
    registrar: MovementRegistrar
    categories: CategoryReader
    pdf: PdfText


@dataclass(frozen=True, slots=True)
class ImportsUnit:
    create: CreateBatch
    get: GetBatch
    confirm: ConfirmBatch
    discard: DiscardBatch
    macro_pdf: StatementReader
    """El lector del resumen PDF de Macro. El del CSV lo arma el pedido con su formato."""


class ImportsUnitFactory(Protocol):
    """La raíz de composición elige la implementación: base real o memoria en tests."""

    def __call__(self) -> AbstractAsyncContextManager[ImportsUnit]: ...


def build_imports_unit(
    batches: BatchRepository,
    rules: RuleRepository,
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
        rules=rules,
        clock=clock,
    )
    return ImportsUnit(
        create=CreateBatch(deps),
        get=GetBatch(deps),
        confirm=ConfirmBatch(deps),
        discard=DiscardBatch(deps),
        macro_pdf=MacroPdfReader(gateways.pdf),
    )
