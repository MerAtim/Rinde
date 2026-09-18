"""Unidad de trabajo de movimientos: los casos de uso de un pedido, con una transacción."""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from rinde.transactions.application.categories import (
    CreateCategory,
    DeleteCategory,
    ListCategories,
    RenameCategory,
)
from rinde.transactions.application.dependencies import TransactionsDependencies
from rinde.transactions.application.use_cases import (
    DeleteTransaction,
    EditTransaction,
    GetTransaction,
    ListBalances,
    ListTransactions,
    RegisterTransaction,
    RestoreTransaction,
)


@dataclass(frozen=True, slots=True)
class TransactionsUnit:
    register: RegisterTransaction
    edit: EditTransaction
    delete: DeleteTransaction
    restore: RestoreTransaction
    get: GetTransaction
    list: ListTransactions
    balances: ListBalances
    categories: ListCategories
    create_category: CreateCategory
    rename_category: RenameCategory
    delete_category: DeleteCategory


class TransactionsUnitFactory(Protocol):
    """La raíz de composición elige la implementación: base real o memoria en tests."""

    def __call__(self) -> AbstractAsyncContextManager[TransactionsUnit]: ...


def build_transactions_unit(deps: TransactionsDependencies) -> TransactionsUnit:
    return TransactionsUnit(
        register=RegisterTransaction(deps),
        edit=EditTransaction(deps),
        delete=DeleteTransaction(deps),
        restore=RestoreTransaction(deps),
        get=GetTransaction(deps),
        list=ListTransactions(deps),
        balances=ListBalances(deps),
        categories=ListCategories(deps),
        create_category=CreateCategory(deps),
        rename_category=RenameCategory(deps),
        delete_category=DeleteCategory(deps),
    )
