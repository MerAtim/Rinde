"""Los hechos que movimientos publica para otros módulos (ADR-0022).

Son su contrato público: viven en la capa de aplicación, que es lo único que
los demás módulos pueden ver. Se publican después de confirmar la transacción.
"""

from dataclasses import dataclass
from datetime import date
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
