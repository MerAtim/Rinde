"""Casos de uso de las compras en cuotas (ADR-0026).

Un plan no es un movimiento: sus cuotas se vuelven movimientos de a una, cuando
llega su fecha. Se generan al crear el plan, en la misma transacción, y cada
vez que se pide lo vencido, que es lo que hace la pantalla al abrirse.
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
from rinde.transactions.application.ports import (
    GeneratedInstallment,
    IdempotentResource,
    RememberedKey,
)
from rinde.transactions.application.use_cases import IDEMPOTENCY_TTL, _account, _category
from rinde.transactions.domain.category import Category
from rinde.transactions.domain.errors import (
    IdempotencyKeyReusedError,
    InstallmentPlanNotFoundError,
)
from rinde.transactions.domain.installments import InstallmentPlan, PlanDraft, plan
from rinde.transactions.domain.transaction import (
    AuditAction,
    Description,
    InstallmentRef,
    Transaction,
    register,
)

_SEPARATOR = "\x1f"


@dataclass(frozen=True, slots=True)
class PlanInput:
    """Lo que llega del borde, ya con tipos, todavía sin reglas de dominio."""

    account_id: UUID
    category_id: UUID
    total: Decimal
    count: int
    first_on: date
    description: str | None = None

    @property
    def fingerprint(self) -> str:
        """Huella del pedido, para distinguir un reintento de una clave reusada."""
        raw = _SEPARATOR.join(
            [
                str(self.account_id),
                str(self.category_id),
                str(self.total),
                str(self.count),
                self.first_on.isoformat(),
                self.description or "",
            ]
        )
        return sha256(raw.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ScheduledInstallment:
    number: int
    due_on: date
    money: Money
    generated: GeneratedInstallment | None
    """El movimiento de esta cuota, si ya se generó."""


@dataclass(frozen=True, slots=True)
class PlanView:
    plan: InstallmentPlan
    installments: list[ScheduledInstallment]

    @property
    def pending(self) -> Money:
        """Lo que falta pagar: las cuotas sin generar de un plan activo."""
        currency = self.plan.total.currency
        if self.plan.is_cancelled:
            return Money.zero(currency)
        return Money.total(
            (item.money for item in self.installments if item.generated is None), currency
        )


def _view(plan: InstallmentPlan, generated: dict[int, GeneratedInstallment]) -> PlanView:
    return PlanView(
        plan=plan,
        installments=[
            ScheduledInstallment(item.number, item.due_on, item.money, generated.get(item.number))
            for item in plan.schedule()
        ],
    )


async def _views(
    deps: TransactionsDependencies, owner_id: UUID, plans: list[InstallmentPlan]
) -> list[PlanView]:
    generated = await deps.installments.generated(owner_id, [item.id for item in plans])
    return [_view(item, generated.get(item.id, {})) for item in plans]


async def _generate(
    deps: TransactionsDependencies,
    owner_id: UUID,
    plans: Collection[InstallmentPlan],
    now: datetime,
) -> list[Transaction]:
    """Las cuotas vencidas que faltan, como movimientos. No confirma.

    La cuenta puede estar archivada: la cuota se debe igual, y archivar no
    deshace la compra.
    """
    today = argentine_day(now)
    pending = [item for item in plans if item.due(today)]
    if not pending:
        return []
    generated = await deps.installments.generated(owner_id, [item.id for item in pending])
    categories: dict[UUID, Category] = {}
    created: list[Transaction] = []
    for item in pending:
        done = generated.get(item.id, {})
        missing = [due for due in item.due(today) if due.number not in done]
        if not missing:
            continue
        account = await deps.accounts.target(item.account_id, owner_id)
        if account is None:
            # Las cuentas no se borran: si no está, no hay dónde registrar.
            continue
        if item.category_id not in categories:
            # Una categoría con un plan no se puede borrar: siempre está.
            categories[item.category_id] = await _category(deps, item.category_id, owner_id)
        for due in missing:
            transaction = register(
                item.draft(due, categories[item.category_id]),
                account,
                transaction_id=uuid4(),
                owner_id=owner_id,
                at=now,
                installment=InstallmentRef(item.id, due.number, item.count),
            )
            if await deps.transactions.add_installment(transaction):
                await deps.audit.record(AuditAction.REGISTERED, transaction, now)
                created.append(transaction)
    return created


class CreateInstallmentPlan:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(
        self, owner_id: UUID, data: PlanInput, idempotency_key: str | None = None
    ) -> PlanView:
        deps = self._deps
        if idempotency_key is not None:
            repeated = await self._repeated(owner_id, data, idempotency_key)
            if repeated is not None:
                return repeated

        account = await _account(deps, data.account_id, owner_id)
        draft = PlanDraft(
            # Money valida la precisión de la moneda: 10,999 pesos no se redondea solo.
            total=Money(data.total, account.currency),
            count=data.count,
            category=await _category(deps, data.category_id, owner_id),
            first_on=data.first_on,
            description=Description.parse(data.description),
        )
        now = deps.clock.now()
        created_plan = plan(draft, account, plan_id=uuid4(), owner_id=owner_id, at=now)
        await deps.installments.add(created_plan)
        # Una compra de hace meses entra con todas las cuotas que ya vencieron.
        created = await _generate(deps, owner_id, [created_plan], now)
        if idempotency_key is not None:
            await deps.idempotency.remember(
                owner_id,
                idempotency_key,
                RememberedKey(
                    data.fingerprint, IdempotentResource.INSTALLMENT_PLAN, created_plan.id
                ),
                now,
            )
            await deps.idempotency.forget_expired(now - IDEMPOTENCY_TTL)
        await deps.transaction.commit()
        await publish_by_month(deps.events, created)
        return (await _views(deps, owner_id, [created_plan]))[0]

    async def _repeated(self, owner_id: UUID, data: PlanInput, key: str) -> PlanView | None:
        """El plan que ya creó esta clave, si el pedido es el mismo."""
        deps = self._deps
        remembered = await deps.idempotency.recall(owner_id, key)
        if remembered is None:
            return None
        if (
            remembered.fingerprint != data.fingerprint
            or remembered.resource is not IdempotentResource.INSTALLMENT_PLAN
        ):
            raise IdempotencyKeyReusedError
        existing = await deps.installments.get(remembered.resource_id, owner_id)
        if existing is None:
            raise InstallmentPlanNotFoundError
        return (await _views(deps, owner_id, [existing]))[0]


class ListInstallmentPlans:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID) -> list[PlanView]:
        plans = await self._deps.installments.list_for_owner(owner_id)
        return await _views(self._deps, owner_id, plans)


class CancelInstallmentPlan:
    """Las cuotas ya generadas quedan, porque pasaron; no se generan más."""

    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, plan_id: UUID) -> PlanView:
        deps = self._deps
        current = await deps.installments.get(plan_id, owner_id)
        if current is None:
            raise InstallmentPlanNotFoundError
        cancelled = current.cancelled(deps.clock.now())
        if cancelled is not current:
            await deps.installments.save(cancelled)
            await deps.transaction.commit()
        return (await _views(deps, owner_id, [cancelled]))[0]


class GenerateDueInstallments:
    """Lo vencido de todos los planes de la persona. Repetirlo no duplica nada."""

    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID) -> list[Transaction]:
        deps = self._deps
        plans = [
            item
            for item in await deps.installments.list_for_owner(owner_id)
            if not item.is_cancelled
        ]
        now = deps.clock.now()
        created = await _generate(deps, owner_id, plans, now)
        if created:
            await deps.transaction.commit()
            await publish_by_month(deps.events, created)
        return created
