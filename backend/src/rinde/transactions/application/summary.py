"""Resumen del libro para reportes: sumas por día, sin un movimiento por fila (ADR-0018).

La base suma y agrupa; acá solo se juntan las dos mitades. Así un período con
decenas de miles de movimientos llega como unas pocas miles de filas.
"""

from datetime import date
from uuid import UUID

from rinde.shared.domain.money import Money
from rinde.transactions.application.dependencies import TransactionsDependencies
from rinde.transactions.application.ports import (
    BalanceChange,
    FlowTotal,
    LedgerScope,
    LedgerSummary,
)


class SummarizeLedger:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, scope: LedgerScope) -> LedgerSummary:
        sums = await self._deps.transactions.flow_sums(owner_id, scope)
        # Una categoría con movimientos no se puede borrar (ADR-0011), así que
        # toda suma tiene la suya.
        categories = {c.id: c for c in await self._deps.categories.list_for_owner(owner_id)}
        flows = [
            FlowTotal(
                day=item.day,
                kind=item.kind,
                category_id=item.category_id,
                category_name=categories[item.category_id].name.value,
                category_slug=categories[item.category_id].slug,
                total=item.total,
            )
            for item in sums
        ]
        # Una transferencia no es gasto ni ingreso, pero sí cambia el saldo de
        # cada cuenta: entra en el patrimonio y no en los flujos.
        changes: dict[tuple[UUID, date | None], Money] = {}
        for change in [
            *await self._deps.transactions.balance_changes(owner_id, scope),
            *await self._deps.transfers.balance_changes(owner_id, scope),
        ]:
            key = (change.account_id, change.month)
            # Todas las filas de una cuenta vienen en su moneda, que es una sola.
            current = changes.get(key)
            changes[key] = change.change if current is None else current + change.change
        return LedgerSummary(
            flows=flows,
            balance_changes=[
                BalanceChange(account_id=account_id, month=month, change=change)
                for (account_id, month), change in changes.items()
            ],
        )
