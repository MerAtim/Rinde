"""Dependencias de los casos de uso de movimientos: repositorios de un pedido."""

from dataclasses import dataclass

from rinde.transactions.application.ports import (
    AccountGateway,
    AuditLog,
    CategoryRepository,
    Clock,
    DatabaseTransaction,
    IdempotencyStore,
    TransactionRepository,
)


@dataclass(frozen=True, slots=True)
class TransactionsDependencies:
    """Todo lo de un pedido comparte la misma transacción de base."""

    transactions: TransactionRepository
    categories: CategoryRepository
    accounts: AccountGateway
    idempotency: IdempotencyStore
    audit: AuditLog
    transaction: DatabaseTransaction
    clock: Clock
