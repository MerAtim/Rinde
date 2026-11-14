"""Casos de uso de los movimientos recurrentes (ADR-0027).

Una regla no es un movimiento: cada vez se vuelve movimiento cuando llega su
fecha. Se genera al crear la regla, en la misma transacción, y cada vez que se
pide lo vencido, que es lo que hace la app al abrirse. Es el mismo mecanismo
que el de las cuotas (ADR-0026).
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from rinde.shared.domain.calendar import argentine_day
from rinde.shared.domain.money import Money
from rinde.transactions.application.dependencies import TransactionsDependencies
from rinde.transactions.application.events import publish_by_month
from rinde.transactions.application.ports import IdempotentResource, RememberedKey
from rinde.transactions.application.use_cases import IDEMPOTENCY_TTL, _account, _category
from rinde.transactions.domain.category import Category, TransactionKind
from rinde.transactions.domain.errors import (
    IdempotencyKeyReusedError,
    RecurringRuleNotFoundError,
)
from rinde.transactions.domain.recurring import (
    Frequency,
    Occurrence,
    RecurringRule,
    RuleDraft,
    recurring_rule,
)
from rinde.transactions.domain.transaction import (
    AuditAction,
    Description,
    RecurrenceRef,
    Transaction,
    register,
)

_SEPARATOR = "\x1f"


@dataclass(frozen=True, slots=True)
class RuleInput:
    """Lo que llega del borde, ya con tipos, todavía sin reglas de dominio."""

    account_id: UUID
    kind: TransactionKind
    amount: Decimal
    category_id: UUID
    frequency: Frequency
    starts_on: date
    description: str | None = None

    @property
    def fingerprint(self) -> str:
        """Huella del pedido, para distinguir un reintento de una clave reusada."""
        raw = _SEPARATOR.join(
            [
                str(self.account_id),
                self.kind.value,
                str(self.amount),
                str(self.category_id),
                self.frequency.value,
                self.starts_on.isoformat(),
                self.description or "",
            ]
        )
        return sha256(raw.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RuleChange:
    """Lo único que se cambia de una regla (ADR-0027, decisión 5)."""

    amount: Decimal
    description: str | None = None


@dataclass(frozen=True, slots=True)
class RuleView:
    rule: RecurringRule
    generated: int
    """Cuántas veces ya se volvió movimiento, borradas incluidas."""
    next: Occurrence | None
    """La próxima que se va a generar, o nada si se canceló."""


async def _views(
    deps: TransactionsDependencies, owner_id: UUID, rules: list[RecurringRule]
) -> list[RuleView]:
    last = await deps.recurring.last_generated(owner_id, [item.id for item in rules])
    return [RuleView(item, last.get(item.id, 0), item.next(last.get(item.id, 0))) for item in rules]


async def _generate(
    deps: TransactionsDependencies,
    owner_id: UUID,
    rules: Collection[RecurringRule],
    now: datetime,
) -> list[Transaction]:
    """Las veces vencidas que faltan, como movimientos. No confirma.

    Una regla de una cuenta archivada no genera nada: archivar es dejar de usarla.
    """
    active = [item for item in rules if not item.is_cancelled]
    if not active:
        return []
    today = argentine_day(now)
    last = await deps.recurring.last_generated(owner_id, [item.id for item in active])
    categories: dict[UUID, Category] = {}
    created: list[Transaction] = []
    for rule in active:
        due = rule.due(last.get(rule.id, 0), today)
        if not due:
            continue
        account = await deps.accounts.target(rule.account_id, owner_id)
        if account is None or account.is_archived:
            continue
        if rule.category_id not in categories:
            # Una categoría con una regla no se puede borrar: siempre está.
            categories[rule.category_id] = await _category(deps, rule.category_id, owner_id)
        for occurrence in due:
            transaction = register(
                rule.draft(occurrence, categories[rule.category_id]),
                account,
                transaction_id=uuid4(),
                owner_id=owner_id,
                at=now,
                recurrence=RecurrenceRef(rule.id, occurrence.number),
            )
            if await deps.transactions.add_occurrence(transaction):
                await deps.audit.record(AuditAction.REGISTERED, transaction, now)
                created.append(transaction)
    return created


async def _owned(deps: TransactionsDependencies, rule_id: UUID, owner_id: UUID) -> RecurringRule:
    rule = await deps.recurring.get(rule_id, owner_id)
    if rule is None:
        raise RecurringRuleNotFoundError
    return rule


class CreateRecurringRule:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(
        self, owner_id: UUID, data: RuleInput, idempotency_key: str | None = None
    ) -> RuleView:
        deps = self._deps
        if idempotency_key is not None:
            repeated = await self._repeated(owner_id, data, idempotency_key)
            if repeated is not None:
                return repeated

        account = await _account(deps, data.account_id, owner_id)
        draft = RuleDraft(
            kind=data.kind,
            # Money valida la precisión de la moneda: 10,999 pesos no se redondea solo.
            money=Money(data.amount, account.currency),
            category=await _category(deps, data.category_id, owner_id),
            frequency=data.frequency,
            starts_on=data.starts_on,
            description=Description.parse(data.description),
        )
        now = deps.clock.now()
        rule = recurring_rule(draft, account, rule_id=uuid4(), owner_id=owner_id, at=now)
        await deps.recurring.add(rule)
        # Una regla que empezó hace meses entra con lo que ya venció.
        created = await _generate(deps, owner_id, [rule], now)
        if idempotency_key is not None:
            await deps.idempotency.remember(
                owner_id,
                idempotency_key,
                RememberedKey(data.fingerprint, IdempotentResource.RECURRING_RULE, rule.id),
                now,
            )
            await deps.idempotency.forget_expired(now - IDEMPOTENCY_TTL)
        await deps.transaction.commit()
        await publish_by_month(deps.events, created)
        return (await _views(deps, owner_id, [rule]))[0]

    async def _repeated(self, owner_id: UUID, data: RuleInput, key: str) -> RuleView | None:
        """La regla que ya creó esta clave, si el pedido es el mismo."""
        deps = self._deps
        remembered = await deps.idempotency.recall(owner_id, key)
        if remembered is None:
            return None
        if (
            remembered.fingerprint != data.fingerprint
            or remembered.resource is not IdempotentResource.RECURRING_RULE
        ):
            raise IdempotencyKeyReusedError
        existing = await _owned(deps, remembered.resource_id, owner_id)
        return (await _views(deps, owner_id, [existing]))[0]


class ListRecurringRules:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID) -> list[RuleView]:
        rules = await self._deps.recurring.list_for_owner(owner_id)
        return await _views(self._deps, owner_id, rules)


class ChangeRecurringRule:
    """El monto nuevo vale desde la próxima vez (ADR-0027, decisión 5).

    Lo que ya venció y faltaba generar se genera antes, con el monto anterior:
    el aumento del alquiler no reescribe los meses que ya pasaron.
    """

    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, rule_id: UUID, data: RuleChange) -> RuleView:
        deps = self._deps
        current = await _owned(deps, rule_id, owner_id)
        changed = current.changed(
            Money(data.amount, current.money.currency), Description.parse(data.description)
        )
        now = deps.clock.now()
        created = await _generate(deps, owner_id, [current], now)
        await deps.recurring.save(changed)
        await deps.transaction.commit()
        await publish_by_month(deps.events, created)
        return (await _views(deps, owner_id, [changed]))[0]


class CancelRecurringRule:
    """Lo ya generado queda, porque pasó; no se genera más."""

    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, rule_id: UUID) -> RuleView:
        deps = self._deps
        current = await _owned(deps, rule_id, owner_id)
        cancelled = current.cancelled(deps.clock.now())
        if cancelled is not current:
            await deps.recurring.save(cancelled)
            await deps.transaction.commit()
        return (await _views(deps, owner_id, [cancelled]))[0]


class GenerateDueRecurring:
    """Lo vencido de todas las reglas de la persona. Repetirlo no duplica nada."""

    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID) -> list[Transaction]:
        deps = self._deps
        rules = await deps.recurring.list_for_owner(owner_id)
        now = deps.clock.now()
        created = await _generate(deps, owner_id, rules, now)
        if created:
            await deps.transaction.commit()
            await publish_by_month(deps.events, created)
        return created
