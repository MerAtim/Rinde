"""Los hechos que movimientos publica para otros módulos (ADR-0022).

Son su contrato público: viven en la capa de aplicación, que es lo único que
los demás módulos pueden ver. Se publican después de confirmar la transacción.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID

from rinde.transactions.domain.category import TransactionKind
from rinde.transactions.domain.transaction import Transaction


@dataclass(frozen=True, slots=True)
class ExpenseRecorded:
    """Un gasto quedó registrado, editado o restaurado: el gasto de su mes pudo subir.

    Borrar no lo publica, porque el gasto solo baja.
    """

    owner_id: UUID
    transaction_id: UUID
    category_id: UUID
    occurred_on: date


def expense_recorded(transaction: Transaction) -> ExpenseRecorded | None:
    if transaction.kind is not TransactionKind.EXPENSE or transaction.is_deleted:
        return None
    return ExpenseRecorded(
        owner_id=transaction.owner_id,
        transaction_id=transaction.id,
        category_id=transaction.category_id,
        occurred_on=transaction.occurred_on,
    )


class _Publisher(Protocol):
    async def publish(self, event: ExpenseRecorded) -> None: ...


async def publish_by_month(publisher: _Publisher, created: Iterable[Transaction]) -> None:
    """Un evento por mes con gastos nuevos, no uno por movimiento.

    Las alertas miden el mes entero (ADR-0022): un lote de cientos de gastos, o
    varias cuotas vencidas juntas, no tiene que medirlo cientos de veces.
    """
    last_by_month: dict[date, Transaction] = {}
    for transaction in created:
        if transaction.kind is TransactionKind.EXPENSE:
            last_by_month[transaction.occurred_on.replace(day=1)] = transaction
    for transaction in last_by_month.values():
        event = expense_recorded(transaction)
        if event is not None:
            await publisher.publish(event)
