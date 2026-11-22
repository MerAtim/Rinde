"""Caso de uso: todo lo que movimientos guarda de una persona (ADR-0034).

Es la parte de movimientos de la exportación de los datos (Ley 25.326, art. 14).
Incluye lo borrado y el historial de cambios, porque también se guardan. Solo
lee: no siembra las categorías de una cuenta que nunca las pidió.
"""

from dataclasses import dataclass
from uuid import UUID

from rinde.transactions.application.dependencies import TransactionsDependencies
from rinde.transactions.application.ports import AuditEntry
from rinde.transactions.domain.category import Category
from rinde.transactions.domain.installments import InstallmentPlan
from rinde.transactions.domain.recurring import RecurringRule
from rinde.transactions.domain.transaction import Transaction
from rinde.transactions.domain.transfer import Transfer


@dataclass(frozen=True, slots=True)
class LedgerExport:
    categories: list[Category]
    transactions: list[Transaction]
    transfers: list[Transfer]
    installment_plans: list[InstallmentPlan]
    recurring_rules: list[RecurringRule]
    transaction_history: list[AuditEntry]
    transfer_history: list[AuditEntry]


class ExportLedger:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID) -> LedgerExport:
        deps = self._deps
        return LedgerExport(
            categories=await deps.categories.list_for_owner(owner_id),
            transactions=await deps.transactions.everything_for_owner(owner_id),
            transfers=await deps.transfers.everything_for_owner(owner_id),
            installment_plans=await deps.installments.list_for_owner(owner_id),
            recurring_rules=await deps.recurring.list_for_owner(owner_id),
            transaction_history=await deps.audit.entries_for_owner(owner_id),
            transfer_history=await deps.transfer_audit.entries_for_owner(owner_id),
        )
