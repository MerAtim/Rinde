"""Repositorio de lotes de importación sobre PostgreSQL. No confirma: lo hace la transacción."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from rinde.imports.domain.batch import BATCH_TTL, BatchLine, ImportBatch, LineStatus
from rinde.imports.domain.rules import CategoryRule
from rinde.imports.domain.statement import LineError, LineProblem
from rinde.imports.infrastructure.tables import category_rules, import_batches, import_lines
from rinde.shared.domain.money import Currency

EXPENSE = "expense"
INCOME = "income"


class SqlAlchemyBatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, batch: ImportBatch) -> None:
        await self._session.execute(
            insert(import_batches).values(
                id=batch.id,
                owner_id=batch.owner_id,
                account_id=batch.account_id,
                currency=batch.currency.value,
                file_name=batch.file_name,
                file_sha256=batch.file_sha256,
                created_at=batch.created_at,
                confirmed_at=batch.confirmed_at,
                imported=batch.imported,
                skipped=batch.skipped,
                errors=[
                    {"line": error.number, "problem": error.problem.value} for error in batch.errors
                ],
            )
        )
        if batch.lines:
            await self._session.execute(
                insert(import_lines),
                [
                    {
                        "batch_id": batch.id,
                        "number": line.number,
                        "occurred_on": line.occurred_on,
                        "description": line.description,
                        "amount": line.signed_amount,
                        "fingerprint": line.fingerprint,
                        "status": line.status.value,
                    }
                    for line in batch.lines
                ],
            )

    async def get(self, batch_id: UUID, owner_id: UUID) -> ImportBatch | None:
        result = await self._session.execute(
            select(import_batches).where(
                import_batches.c.id == batch_id, import_batches.c.owner_id == owner_id
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        currency = Currency(row["currency"])
        lines = await self._session.execute(
            select(import_lines)
            .where(import_lines.c.batch_id == batch_id)
            .order_by(import_lines.c.number)
        )
        return ImportBatch(
            id=row["id"],
            owner_id=row["owner_id"],
            account_id=row["account_id"],
            currency=currency,
            file_name=row["file_name"],
            file_sha256=row["file_sha256"],
            created_at=row["created_at"],
            confirmed_at=row["confirmed_at"],
            imported=row["imported"],
            skipped=row["skipped"],
            errors=[
                LineError(int(item["line"]), LineProblem(item["problem"])) for item in row["errors"]
            ],
            lines=[
                BatchLine(
                    number=line["number"],
                    occurred_on=line["occurred_on"],
                    description=line["description"],
                    # La columna tiene la escala de Bitcoin; se ajusta a la de la moneda.
                    signed_amount=Decimal(line["amount"]).quantize(currency.quantum),
                    fingerprint=line["fingerprint"],
                    status=LineStatus(line["status"]),
                )
                for line in lines.mappings()
            ],
        )

    async def save_confirmation(self, batch: ImportBatch) -> None:
        await self._session.execute(
            update(import_batches)
            .where(import_batches.c.id == batch.id, import_batches.c.owner_id == batch.owner_id)
            .values(confirmed_at=batch.confirmed_at, imported=batch.imported, skipped=batch.skipped)
        )

    async def delete(self, batch_id: UUID, owner_id: UUID) -> bool:
        result = await self._session.execute(
            delete(import_batches)
            .where(
                import_batches.c.id == batch_id,
                import_batches.c.owner_id == owner_id,
                import_batches.c.confirmed_at.is_(None),
            )
            .returning(import_batches.c.id)
        )
        return result.first() is not None

    async def delete_expired(self, now: datetime) -> None:
        # Las líneas se van en cascada.
        await self._session.execute(
            delete(import_batches).where(
                import_batches.c.confirmed_at.is_(None),
                import_batches.c.created_at <= now - BATCH_TTL,
            )
        )


class SqlAlchemyRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def for_owner(self, owner_id: UUID) -> list[CategoryRule]:
        result = await self._session.execute(
            select(category_rules).where(category_rules.c.owner_id == owner_id)
        )
        return [
            CategoryRule(
                id=row["id"],
                owner_id=row["owner_id"],
                pattern=row["pattern"],
                category_id=row["category_id"],
                is_expense=row["kind"] == EXPENSE,
                updated_at=row["updated_at"],
            )
            for row in result.mappings()
        ]

    async def save(self, rule: CategoryRule) -> None:
        statement = pg_insert(category_rules).values(
            id=rule.id,
            owner_id=rule.owner_id,
            category_id=rule.category_id,
            kind=EXPENSE if rule.is_expense else INCOME,
            pattern=rule.pattern,
            updated_at=rule.updated_at,
        )
        # El mismo texto en el mismo tipo reemplaza la categoría (ADR-0024).
        await self._session.execute(
            statement.on_conflict_do_update(
                constraint="uq_category_rules_owner_kind_pattern",
                set_={
                    "category_id": statement.excluded.category_id,
                    "updated_at": statement.excluded.updated_at,
                },
            )
        )
