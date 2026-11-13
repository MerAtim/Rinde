"""Adaptadores hacia movimientos: importación lo usa por su capa de aplicación.

Cada adaptador abre su propia unidad de trabajo de movimientos y la cierra al
terminar. Registrar un lote es la única escritura, y movimientos la confirma en
su propia transacción (ADR-0023).
"""

from datetime import date
from uuid import UUID

from rinde.imports.application.ports import CategoryInfo, LineToRegister, Registered
from rinde.imports.domain.batch import AccountState, ExistingMovement
from rinde.transactions.application.imported import ImportedLine
from rinde.transactions.application.unit import TransactionsUnitFactory

# El tipo se compara por su valor: el dominio de movimientos no se importa directo.
EXPENSE = "expense"


class TransactionsAccountInspector:
    def __init__(self, factory: TransactionsUnitFactory) -> None:
        self._factory = factory

    async def inspect(
        self, owner_id: UUID, account_id: UUID, fingerprints: list[str], period: tuple[date, date]
    ) -> AccountState:
        async with self._factory() as unit:
            activity = await unit.inspect_import.execute(owner_id, account_id, fingerprints, period)
        return AccountState(
            currency=activity.currency,
            imported=activity.imported,
            existing=[
                ExistingMovement(item.occurred_on, item.signed_amount)
                for item in activity.movements
            ],
        )


class TransactionsRegistrar:
    def __init__(self, factory: TransactionsUnitFactory) -> None:
        self._factory = factory

    async def register(
        self, owner_id: UUID, account_id: UUID, lines: list[LineToRegister]
    ) -> Registered:
        async with self._factory() as unit:
            outcome = await unit.register_imported.execute(
                owner_id,
                account_id,
                [
                    ImportedLine(
                        signed_amount=line.signed_amount,
                        category_id=line.category_id,
                        occurred_on=line.occurred_on,
                        description=line.description,
                        fingerprint=line.fingerprint,
                    )
                    for line in lines
                ],
            )
        return Registered(imported=len(outcome.created), skipped=len(outcome.skipped))


class TransactionsCategoryReader:
    def __init__(self, factory: TransactionsUnitFactory) -> None:
        self._factory = factory

    async def categories(self, owner_id: UUID) -> list[CategoryInfo]:
        async with self._factory() as unit:
            categories = await unit.categories.execute(owner_id)
        return [
            CategoryInfo(
                id=category.id, slug=category.slug, is_expense=category.kind.value == EXPENSE
            )
            for category in categories
        ]
