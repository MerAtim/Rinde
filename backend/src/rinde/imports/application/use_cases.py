"""Casos de uso de importación. Todos reciben el dueño: es el filtro de autorización."""

import asyncio
from dataclasses import dataclass, replace
from hashlib import sha256
from uuid import UUID, uuid4

from rinde.imports.application.ports import (
    AccountInspector,
    BatchRepository,
    CategoryReader,
    Clock,
    LineToRegister,
    MovementRegistrar,
    RuleRepository,
    StatementReader,
    Transaction,
)
from rinde.imports.domain.batch import ImportBatch, LineStatus, classify, fingerprints
from rinde.imports.domain.errors import (
    ImportBatchNotFoundError,
    ImportCurrencyMismatchError,
    ImportFileTooLargeError,
    ImportLineNotFoundError,
)
from rinde.imports.domain.rules import CategoryRule, best_rule, pattern_from
from rinde.imports.domain.statement import MAX_BYTES
from rinde.shared.domain.calendar import argentine_day

FILE_NAME_LENGTH = 255

# Sin una regla, cada línea arranca en la categoría "otros" de su tipo, que se
# siembra con la cuenta (ADR-0011). La persona la cambia en la vista previa.
DEFAULT_EXPENSE = "otros"
DEFAULT_INCOME = "otros-ingresos"


@dataclass(frozen=True, slots=True)
class ImportsDependencies:
    batches: BatchRepository
    transaction: Transaction
    accounts: AccountInspector
    registrar: MovementRegistrar
    categories: CategoryReader
    rules: RuleRepository
    clock: Clock


@dataclass(frozen=True, slots=True)
class Suggestion:
    category_id: UUID | None
    rule: str | None
    """El texto de la regla que la eligió, o `None` si es la de "otros" (ADR-0024)."""


@dataclass(frozen=True, slots=True)
class BatchPreview:
    batch: ImportBatch
    suggestions: dict[int, Suggestion]
    """La categoría propuesta para cada línea, por número de línea."""


async def _preview(deps: ImportsDependencies, batch: ImportBatch) -> BatchPreview:
    by_slug = {
        (item.slug, item.is_expense): item.id
        for item in await deps.categories.categories(batch.owner_id)
        if item.slug
    }
    defaults = {
        True: by_slug.get((DEFAULT_EXPENSE, True)),
        False: by_slug.get((DEFAULT_INCOME, False)),
    }
    rules = await deps.rules.for_owner(batch.owner_id)
    suggestions = {}
    for line in batch.lines:
        is_expense = line.signed_amount < 0
        rule = best_rule(rules, line.description, is_expense)
        suggestions[line.number] = (
            Suggestion(rule.category_id, rule.pattern)
            if rule
            else Suggestion(defaults[is_expense], None)
        )
    return BatchPreview(batch, suggestions)


async def _owned(deps: ImportsDependencies, batch_id: UUID, owner_id: UUID) -> ImportBatch:
    batch = await deps.batches.get(batch_id, owner_id)
    if batch is None or batch.is_expired(deps.clock.now()):
        raise ImportBatchNotFoundError
    return batch


class CreateBatch:
    """Lee el archivo y guarda el lote, sin tocar todavía la cuenta."""

    def __init__(self, deps: ImportsDependencies) -> None:
        self._deps = deps

    async def execute(
        self,
        owner_id: UUID,
        account_id: UUID,
        file_name: str,
        content: bytes,
        reader: StatementReader,
    ) -> BatchPreview:
        deps = self._deps
        if len(content) > MAX_BYTES:
            raise ImportFileTooLargeError
        # Leer es trabajo de CPU (un PDF, sobre todo): en un hilo, para no frenar
        # los otros pedidos mientras tanto.
        statement = await asyncio.to_thread(reader.read, content)
        hashes = fingerprints(account_id, statement.lines)
        dates = [line.occurred_on for line in statement.lines]
        account = await deps.accounts.inspect(
            owner_id, account_id, hashes, (min(dates), max(dates))
        )
        if statement.currency is not None and statement.currency != account.currency:
            raise ImportCurrencyMismatchError
        now = deps.clock.now()
        classified = classify(statement, hashes, account, argentine_day(now))
        batch = ImportBatch(
            id=uuid4(),
            owner_id=owner_id,
            account_id=account_id,
            currency=account.currency,
            # El nombre es solo para reconocerlo: no se usa como ruta en ningún lado.
            file_name=" ".join(file_name.split())[:FILE_NAME_LENGTH] or "archivo",
            file_sha256=sha256(content).hexdigest(),
            created_at=now,
            lines=classified.lines,
            errors=classified.errors,
        )
        await deps.batches.delete_expired(now)
        await deps.batches.add(batch)
        await deps.transaction.commit()
        return await _preview(deps, batch)


class GetBatch:
    def __init__(self, deps: ImportsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, batch_id: UUID) -> BatchPreview:
        return await _preview(self._deps, await _owned(self._deps, batch_id, owner_id))


@dataclass(frozen=True, slots=True)
class Choice:
    number: int
    category_id: UUID
    remember: str | None = None
    """Un texto para recordar esta categoría en las próximas importaciones (ADR-0024)."""


@dataclass(frozen=True, slots=True)
class Confirmation:
    imported: int
    skipped: int


class ConfirmBatch:
    """Registra las líneas elegidas. Confirmar otra vez devuelve lo mismo y no duplica."""

    def __init__(self, deps: ImportsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, batch_id: UUID, choices: list[Choice]) -> Confirmation:
        deps = self._deps
        batch = await _owned(deps, batch_id, owner_id)
        if batch.confirmed_at is not None:
            return Confirmation(batch.imported, batch.skipped)
        lines = {line.number: line for line in batch.lines}
        to_register = []
        # Se validan antes de registrar nada: un texto inválido no deja un lote a medias.
        rules: dict[tuple[str, bool], CategoryRule] = {}
        now = deps.clock.now()
        for choice in choices:
            line = lines.get(choice.number)
            if line is None:
                raise ImportLineNotFoundError
            if choice.remember is not None:
                rule = CategoryRule(
                    id=uuid4(),
                    owner_id=owner_id,
                    pattern=pattern_from(choice.remember),
                    category_id=choice.category_id,
                    is_expense=line.signed_amount < 0,
                    updated_at=now,
                )
                # El mismo texto dos veces en un lote: vale la última elección.
                rules[(rule.pattern, rule.is_expense)] = rule
            # Un duplicado ya entró: movimientos lo saltearía igual, pero no se manda.
            if line.status is LineStatus.DUPLICATE:
                continue
            to_register.append(
                LineToRegister(
                    signed_amount=line.signed_amount,
                    category_id=choice.category_id,
                    occurred_on=line.occurred_on,
                    description=line.description,
                    fingerprint=line.fingerprint,
                )
            )
        # Movimientos confirma su transacción y después se marca el lote. Si algo
        # se corta en el medio, confirmar de nuevo saltea lo que ya entró (ADR-0023).
        registered = await deps.registrar.register(owner_id, batch.account_id, to_register)
        confirmed = replace(
            batch,
            confirmed_at=now,
            imported=registered.imported,
            skipped=registered.skipped,
        )
        await deps.batches.save_confirmation(confirmed)
        # En la misma transacción que el lote: si no se confirma, no se recuerda.
        for rule in rules.values():
            await deps.rules.save(rule)
        await deps.transaction.commit()
        return Confirmation(registered.imported, registered.skipped)


class DiscardBatch:
    """Solo un lote sin confirmar: uno confirmado es la constancia del origen de sus movimientos."""

    def __init__(self, deps: ImportsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, batch_id: UUID) -> None:
        deps = self._deps
        if not await deps.batches.delete(batch_id, owner_id):
            raise ImportBatchNotFoundError
        await deps.transaction.commit()
