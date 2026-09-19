"""Fakes en memoria de los puertos de movimientos.

Son fakes y no mocks: se comportan como la cosa real (guardan, filtran, ordenan),
así los tests describen reglas y no llamadas.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from rinde.shared.domain.money import Currency, Money
from rinde.transactions.application.dependencies import TransactionsDependencies
from rinde.transactions.application.pagination import Cursor
from rinde.transactions.application.ports import (
    AccountBalance,
    Page,
    RememberedKey,
    TransactionFilters,
    TransferFilters,
    TransferPage,
)
from rinde.transactions.application.unit import TransactionsUnit, build_transactions_unit
from rinde.transactions.domain.category import Category, TransactionKind
from rinde.transactions.domain.transaction import AuditAction, TargetAccount, Transaction
from rinde.transactions.domain.transfer import Transfer


class FakeClock:
    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2026, 9, 18, 12, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, **kwargs: float) -> None:
        self._now += timedelta(**kwargs)


class FakeDatabaseTransaction:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeTransactionRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Transaction] = {}

    async def add(self, transaction: Transaction) -> None:
        self.rows[transaction.id] = transaction

    async def get(self, transaction_id: UUID, owner_id: UUID) -> Transaction | None:
        found = self.rows.get(transaction_id)
        return found if found and found.owner_id == owner_id else None

    def _alive(self, owner_id: UUID) -> list[Transaction]:
        """Como el repositorio real: toda lectura parte de acá y excluye borrados."""
        return [
            row for row in self.rows.values() if row.owner_id == owner_id and not row.is_deleted
        ]

    async def page_for_owner(
        self, owner_id: UUID, filters: TransactionFilters, *, cursor: str | None, limit: int
    ) -> Page:
        rows = self._alive(owner_id)
        if filters.account_id is not None:
            rows = [row for row in rows if row.account_id == filters.account_id]
        if filters.since is not None:
            rows = [row for row in rows if row.occurred_on >= filters.since]
        if filters.until is not None:
            rows = [row for row in rows if row.occurred_on <= filters.until]
        rows.sort(key=lambda row: (row.occurred_on, row.id), reverse=True)
        if cursor is not None:
            mark = Cursor.decode(cursor)
            rows = [
                row for row in rows if (row.occurred_on, row.id) < (mark.occurred_on, mark.row_id)
            ]
        page, rest = rows[:limit], rows[limit:]
        next_cursor = Cursor(page[-1].occurred_on, page[-1].id).encode() if page and rest else None
        return Page(items=page, next_cursor=next_cursor)

    async def balances_for_owner(self, owner_id: UUID) -> list[AccountBalance]:
        totals: dict[UUID, Money] = {}
        for row in self._alive(owner_id):
            current = totals.get(row.account_id, Money.zero(row.money.currency))
            totals[row.account_id] = current + row.signed_amount
        return [AccountBalance(account_id, balance) for account_id, balance in totals.items()]

    async def count_by_category(self, category_id: UUID, owner_id: UUID) -> int:
        return len([row for row in self._alive(owner_id) if row.category_id == category_id])

    async def save(self, transaction: Transaction) -> None:
        self.rows[transaction.id] = transaction


class FakeCategoryRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Category] = {}

    async def add(self, category: Category) -> None:
        self.rows[category.id] = category

    async def add_seeds(self, categories: list[Category]) -> None:
        for category in categories:
            taken = await self.find_by_name(
                category.owner_id, category.name.comparable, category.kind
            )
            if taken is None:
                self.rows[category.id] = category

    async def get(self, category_id: UUID, owner_id: UUID) -> Category | None:
        found = self.rows.get(category_id)
        return found if found and found.owner_id == owner_id else None

    async def list_for_owner(self, owner_id: UUID) -> list[Category]:
        rows = [row for row in self.rows.values() if row.owner_id == owner_id]
        return sorted(rows, key=lambda row: row.name.comparable)

    async def find_by_name(
        self, owner_id: UUID, comparable: str, kind: TransactionKind
    ) -> Category | None:
        for row in self.rows.values():
            if row.owner_id == owner_id and row.kind is kind and row.name.comparable == comparable:
                return row
        return None

    async def save(self, category: Category) -> None:
        self.rows[category.id] = category

    async def delete(self, category_id: UUID, owner_id: UUID) -> None:
        found = self.rows.get(category_id)
        if found and found.owner_id == owner_id:
            del self.rows[category_id]


class FakeAccountGateway:
    """Las cuentas que existen para movimientos, con su moneda y su estado."""

    def __init__(self) -> None:
        self.accounts: dict[tuple[UUID, UUID], TargetAccount] = {}

    def add(
        self,
        account_id: UUID,
        owner_id: UUID,
        currency: Currency = Currency.ARS,
        *,
        archived: bool = False,
    ) -> TargetAccount:
        account = TargetAccount(id=account_id, currency=currency, is_archived=archived)
        self.accounts[(account_id, owner_id)] = account
        return account

    async def target(self, account_id: UUID, owner_id: UUID) -> TargetAccount | None:
        return self.accounts.get((account_id, owner_id))


class FakeIdempotencyStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str], tuple[RememberedKey, datetime]] = {}

    async def remember(
        self, owner_id: UUID, key: str, remembered: RememberedKey, at: datetime
    ) -> None:
        self.rows[(owner_id, key)] = (remembered, at)

    async def recall(self, owner_id: UUID, key: str) -> RememberedKey | None:
        found = self.rows.get((owner_id, key))
        return found[0] if found else None

    async def forget_expired(self, before: datetime) -> None:
        self.rows = {key: row for key, row in self.rows.items() if row[1] >= before}


class FakeTransferRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Transfer] = {}

    async def add(self, transfer: Transfer) -> None:
        self.rows[transfer.id] = transfer

    async def get(self, transfer_id: UUID, owner_id: UUID) -> Transfer | None:
        found = self.rows.get(transfer_id)
        return found if found and found.owner_id == owner_id else None

    def _alive(self, owner_id: UUID) -> list[Transfer]:
        return [
            row for row in self.rows.values() if row.owner_id == owner_id and not row.is_deleted
        ]

    async def page_for_owner(
        self, owner_id: UUID, filters: TransferFilters, *, cursor: str | None, limit: int
    ) -> TransferPage:
        rows = self._alive(owner_id)
        if filters.account_id is not None:
            # La cuenta vale de los dos lados: lo que le entro y lo que le salio.
            rows = [
                row
                for row in rows
                if filters.account_id in (row.from_account_id, row.to_account_id)
            ]
        if filters.since is not None:
            rows = [row for row in rows if row.occurred_on >= filters.since]
        if filters.until is not None:
            rows = [row for row in rows if row.occurred_on <= filters.until]
        rows.sort(key=lambda row: (row.occurred_on, row.id), reverse=True)
        if cursor is not None:
            mark = Cursor.decode(cursor)
            rows = [
                row for row in rows if (row.occurred_on, row.id) < (mark.occurred_on, mark.row_id)
            ]
        page, rest = rows[:limit], rows[limit:]
        next_cursor = Cursor(page[-1].occurred_on, page[-1].id).encode() if page and rest else None
        return TransferPage(items=page, next_cursor=next_cursor)

    async def balances_for_owner(self, owner_id: UUID) -> list[AccountBalance]:
        totals: dict[UUID, Money] = {}
        for row in self._alive(owner_id):
            for account_id in (row.from_account_id, row.to_account_id):
                effect = row.effect_on(account_id)
                if effect is None:
                    continue
                current = totals.get(account_id)
                totals[account_id] = effect if current is None else current + effect
        return [
            AccountBalance(account_id=account_id, balance=total)
            for account_id, total in totals.items()
        ]

    async def save(self, transfer: Transfer) -> None:
        self.rows[transfer.id] = transfer


class FakeTransferAuditLog:
    def __init__(self) -> None:
        self.entries: list[tuple[AuditAction, UUID, datetime]] = []

    async def record(self, action: AuditAction, transfer: Transfer, at: datetime) -> None:
        self.entries.append((action, transfer.id, at))

    @property
    def actions(self) -> list[AuditAction]:
        return [action for action, _, _ in self.entries]


class FakeAuditLog:
    def __init__(self) -> None:
        self.entries: list[tuple[AuditAction, UUID, datetime]] = []

    async def record(self, action: AuditAction, transaction: Transaction, at: datetime) -> None:
        self.entries.append((action, transaction.id, at))

    @property
    def actions(self) -> list[AuditAction]:
        return [action for action, _, _ in self.entries]


def a_date(day: int = 18) -> date:
    return date(2026, 9, day)


class Harness:
    """Una unidad de trabajo con todos los puertos en memoria, para los tests."""

    def __init__(self) -> None:
        self.clock = FakeClock()
        self.transactions = FakeTransactionRepository()
        self.transfers = FakeTransferRepository()
        self.categories = FakeCategoryRepository()
        self.accounts = FakeAccountGateway()
        self.idempotency = FakeIdempotencyStore()
        self.audit = FakeAuditLog()
        self.transfer_audit = FakeTransferAuditLog()
        self.db = FakeDatabaseTransaction()
        self.unit: TransactionsUnit = build_transactions_unit(
            TransactionsDependencies(
                transactions=self.transactions,
                transfers=self.transfers,
                categories=self.categories,
                accounts=self.accounts,
                idempotency=self.idempotency,
                audit=self.audit,
                transfer_audit=self.transfer_audit,
                transaction=self.db,
                clock=self.clock,
            )
        )
