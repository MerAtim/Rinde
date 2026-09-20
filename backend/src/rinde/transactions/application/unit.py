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
    DeleteTransfer,
    EditTransaction,
    EditTransfer,
    GetTransaction,
    GetTransfer,
    ListBalances,
    ListHistory,
    ListTransactions,
    ListTransfers,
    RegisterTransaction,
    RegisterTransfer,
    RestoreTransaction,
    RestoreTransfer,
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
    history: ListHistory
    register_transfer: RegisterTransfer
    edit_transfer: EditTransfer
    delete_transfer: DeleteTransfer
    restore_transfer: RestoreTransfer
    get_transfer: GetTransfer
    list_transfers: ListTransfers
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
        history=ListHistory(deps),
        register_transfer=RegisterTransfer(deps),
        edit_transfer=EditTransfer(deps),
        delete_transfer=DeleteTransfer(deps),
        restore_transfer=RestoreTransfer(deps),
        get_transfer=GetTransfer(deps),
        list_transfers=ListTransfers(deps),
        categories=ListCategories(deps),
        create_category=CreateCategory(deps),
        rename_category=RenameCategory(deps),
        delete_category=DeleteCategory(deps),
    )
