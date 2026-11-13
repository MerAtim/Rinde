"""Piezas en memoria para probar importación sin base ni otros módulos."""

from dataclasses import replace
from datetime import date, datetime
from uuid import UUID

from rinde.imports.application.ports import (
    CategoryInfo,
    LineToRegister,
    Registered,
)
from rinde.imports.domain.batch import BATCH_TTL, AccountState, ImportBatch
from rinde.imports.domain.rules import CategoryRule
from rinde.shared.domain.money import Currency


class InMemoryBatchRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, ImportBatch] = {}

    async def add(self, batch: ImportBatch) -> None:
        self.rows[batch.id] = batch

    async def get(self, batch_id: UUID, owner_id: UUID) -> ImportBatch | None:
        found = self.rows.get(batch_id)
        return found if found and found.owner_id == owner_id else None

    async def save_confirmation(self, batch: ImportBatch) -> None:
        self.rows[batch.id] = replace(
            self.rows[batch.id],
            confirmed_at=batch.confirmed_at,
            imported=batch.imported,
            skipped=batch.skipped,
        )

    async def delete(self, batch_id: UUID, owner_id: UUID) -> bool:
        found = await self.get(batch_id, owner_id)
        if found is None or found.confirmed_at is not None:
            return False
        del self.rows[batch_id]
        return True

    async def delete_expired(self, now: datetime) -> None:
        self.rows = {
            key: batch
            for key, batch in self.rows.items()
            if batch.confirmed_at is not None or batch.created_at > now - BATCH_TTL
        }


class InMemoryRuleRepository:
    """Con la misma regla que la restricción única: texto y tipo por persona."""

    def __init__(self) -> None:
        self.rows: list[CategoryRule] = []

    async def for_owner(self, owner_id: UUID) -> list[CategoryRule]:
        return [rule for rule in self.rows if rule.owner_id == owner_id]

    async def save(self, rule: CategoryRule) -> None:
        key = (rule.owner_id, rule.pattern, rule.is_expense)
        for index, row in enumerate(self.rows):
            if (row.owner_id, row.pattern, row.is_expense) == key:
                self.rows[index] = replace(
                    row, category_id=rule.category_id, updated_at=rule.updated_at
                )
                return
        self.rows.append(rule)


class FakeAccount:
    """Una cuenta de una persona, con lo que ya tiene y lo que se registra."""

    def __init__(self, owner_id: UUID, account_id: UUID, state: AccountState | None = None) -> None:
        self.owner_id = owner_id
        self.account_id = account_id
        self.state = state or AccountState(Currency.ARS, set(), [])
        self.registered: list[LineToRegister] = []
        self.periods: list[tuple[date, date]] = []

    async def inspect(
        self, owner_id: UUID, account_id: UUID, fingerprints: list[str], period: tuple[date, date]
    ) -> AccountState:
        self._check(owner_id, account_id)
        self.periods.append(period)
        return replace(self.state, imported=self.state.imported & set(fingerprints))

    async def register(
        self, owner_id: UUID, account_id: UUID, lines: list[LineToRegister]
    ) -> Registered:
        self._check(owner_id, account_id)
        new = [line for line in lines if line.fingerprint not in self.state.imported]
        self.registered.extend(new)
        self.state = replace(
            self.state, imported=self.state.imported | {line.fingerprint for line in new}
        )
        return Registered(imported=len(new), skipped=len(lines) - len(new))

    def _check(self, owner_id: UUID, account_id: UUID) -> None:
        if (owner_id, account_id) != (self.owner_id, self.account_id):
            raise LookupError("cuenta ajena")


class FixedCategories:
    def __init__(self, owner_id: UUID, *categories: CategoryInfo) -> None:
        self._owner_id = owner_id
        self.items = list(categories)

    async def categories(self, owner_id: UUID) -> list[CategoryInfo]:
        return list(self.items) if owner_id == self._owner_id else []
