"""Movimientos que llegan de un archivo importado (ADR-0023).

Movimientos no sabe leer archivos: eso es del módulo de importación. Acá solo
se consulta qué ya entró en una cuenta y se registra un lote de líneas, con las
mismas reglas, la misma auditoría y el mismo evento que un movimiento cargado a
mano.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from rinde.shared.domain.money import Currency, Money
from rinde.transactions.application.dependencies import TransactionsDependencies
from rinde.transactions.application.events import expense_recorded
from rinde.transactions.application.use_cases import _account, _category
from rinde.transactions.domain.category import Category, TransactionKind
from rinde.transactions.domain.transaction import (
    AuditAction,
    Description,
    Draft,
    Transaction,
    register,
)


@dataclass(frozen=True, slots=True)
class KnownMovement:
    """Un movimiento que ya está en la cuenta, para marcar un posible duplicado."""

    occurred_on: date
    signed_amount: Decimal
    """Negativo si es un gasto."""


@dataclass(frozen=True, slots=True)
class AccountActivity:
    currency: Currency
    imported: set[str]
    """Las huellas de esa cuenta que ya entraron."""
    movements: list[KnownMovement]
    """Los vivos de la cuenta en el período del archivo."""


class InspectImport:
    """Lo que la vista previa necesita saber de la cuenta para marcar duplicados."""

    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(
        self,
        owner_id: UUID,
        account_id: UUID,
        fingerprints: list[str],
        period: tuple[date, date],
    ) -> AccountActivity:
        deps = self._deps
        account = await _account(deps, account_id, owner_id)
        since, until = period
        return AccountActivity(
            currency=account.currency,
            imported=await deps.transactions.imported_fingerprints(
                owner_id, account_id, fingerprints
            ),
            movements=[
                KnownMovement(item.occurred_on, item.signed_amount.amount)
                for item in await deps.transactions.in_account_between(
                    owner_id, account_id, since, until
                )
            ],
        )


@dataclass(frozen=True, slots=True)
class ImportedLine:
    signed_amount: Decimal
    """Negativo, un gasto; positivo, un ingreso. Cero no llega hasta acá."""
    category_id: UUID
    occurred_on: date
    description: str | None
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ImportOutcome:
    created: list[Transaction]
    skipped: list[str]
    """Huellas que ya estaban: confirmar otra vez el mismo lote no duplica."""


class RegisterImported:
    """Registra las líneas de un lote en una sola transacción: entran todas o ninguna."""

    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(
        self, owner_id: UUID, account_id: UUID, lines: list[ImportedLine]
    ) -> ImportOutcome:
        deps = self._deps
        account = await _account(deps, account_id, owner_id)
        known = await deps.transactions.imported_fingerprints(
            owner_id, account_id, [line.fingerprint for line in lines]
        )
        categories: dict[UUID, Category] = {}
        created: list[Transaction] = []
        skipped: list[str] = []
        now = deps.clock.now()
        for line in lines:
            if line.fingerprint in known:
                skipped.append(line.fingerprint)
                continue
            known.add(line.fingerprint)
            if line.category_id not in categories:
                categories[line.category_id] = await _category(deps, line.category_id, owner_id)
            kind = TransactionKind.EXPENSE if line.signed_amount < 0 else TransactionKind.INCOME
            draft = Draft(
                kind=kind,
                money=Money(abs(line.signed_amount), account.currency),
                category=categories[line.category_id],
                occurred_on=line.occurred_on,
                description=Description.parse(line.description),
            )
            transaction = register(
                draft,
                account,
                transaction_id=uuid4(),
                owner_id=owner_id,
                at=now,
                source_fingerprint=line.fingerprint,
            )
            await deps.transactions.add(transaction)
            await deps.audit.record(AuditAction.REGISTERED, transaction, now)
            created.append(transaction)
        if created:
            await deps.transaction.commit()
        # Después de confirmar, como un movimiento cargado a mano (ADR-0022). Uno
        # por mes y no por línea: las alertas miden el mes entero, y un archivo
        # de cientos de gastos no tiene que medirlo cientos de veces.
        last_by_month: dict[date, Transaction] = {}
        for transaction in created:
            if transaction.kind is TransactionKind.EXPENSE:
                last_by_month[transaction.occurred_on.replace(day=1)] = transaction
        for transaction in last_by_month.values():
            event = expense_recorded(transaction)
            if event is not None:
                await deps.events.publish(event)
        return ImportOutcome(created, skipped)
