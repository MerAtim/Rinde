"""Adaptador de la demo: escribe por la capa de aplicación de cada módulo.

Cada operación abre la unidad de trabajo de su módulo y la cierra al terminar,
así una demo se carga con las mismas reglas, la misma auditoría y los mismos
eventos que si la cargara una persona. Los tipos de la demo se traducen a los
de cada dominio por su valor.
"""

from uuid import UUID

from rinde.accounts.application.unit import AccountsUnitFactory
from rinde.accounts.domain.account import AccountKind
from rinde.budgets.application.unit import BudgetsUnitFactory
from rinde.demo.application.ports import (
    AccountType,
    Entry,
    PlanEntry,
    RuleEntry,
    TransferEntry,
)
from rinde.shared.domain.money import Currency, Money
from rinde.transactions.application.installments import PlanInput
from rinde.transactions.application.recurring import RuleInput
from rinde.transactions.application.unit import TransactionsUnitFactory
from rinde.transactions.application.use_cases import TransactionInput, TransferInput
from rinde.transactions.domain.category import TransactionKind
from rinde.transactions.domain.recurring import Frequency


class ModulesDemoWriter:
    def __init__(
        self,
        accounts: AccountsUnitFactory,
        transactions: TransactionsUnitFactory,
        budgets: BudgetsUnitFactory,
    ) -> None:
        self._accounts = accounts
        self._transactions = transactions
        self._budgets = budgets

    async def open_account(
        self, owner_id: UUID, name: str, kind: AccountType, currency: Currency
    ) -> UUID:
        async with self._accounts() as unit:
            account = await unit.open.execute(owner_id, name, AccountKind(kind.value), currency)
        return account.id

    async def categories(self, owner_id: UUID) -> dict[str, UUID]:
        async with self._transactions() as unit:
            listed = await unit.categories.execute(owner_id)
        return {category.slug: category.id for category in listed if category.slug is not None}

    async def set_budget(self, owner_id: UUID, category_id: UUID, limit: Money) -> None:
        async with self._budgets() as unit:
            await unit.set.execute(owner_id, category_id, limit)

    async def record(self, owner_id: UUID, entry: Entry) -> None:
        async with self._transactions() as unit:
            await unit.register.execute(
                owner_id,
                TransactionInput(
                    account_id=entry.account_id,
                    kind=TransactionKind(entry.kind.value),
                    amount=entry.amount,
                    category_id=entry.category_id,
                    occurred_on=entry.on,
                    description=entry.description,
                ),
            )

    async def transfer(self, owner_id: UUID, entry: TransferEntry) -> None:
        async with self._transactions() as unit:
            await unit.register_transfer.execute(
                owner_id,
                TransferInput(
                    from_account_id=entry.from_account_id,
                    to_account_id=entry.to_account_id,
                    sent=entry.sent,
                    received=entry.received,
                    occurred_on=entry.on,
                    description=entry.description,
                ),
            )

    async def installments(self, owner_id: UUID, entry: PlanEntry) -> None:
        async with self._transactions() as unit:
            await unit.create_plan.execute(
                owner_id,
                PlanInput(
                    account_id=entry.account_id,
                    category_id=entry.category_id,
                    total=entry.total,
                    count=entry.count,
                    first_on=entry.first_on,
                    description=entry.description,
                ),
            )

    async def recurring(self, owner_id: UUID, entry: RuleEntry) -> None:
        async with self._transactions() as unit:
            await unit.create_rule.execute(
                owner_id,
                RuleInput(
                    account_id=entry.account_id,
                    kind=TransactionKind(entry.kind.value),
                    amount=entry.amount,
                    category_id=entry.category_id,
                    frequency=Frequency.MONTHLY,
                    starts_on=entry.starts_on,
                    description=entry.description,
                ),
            )
