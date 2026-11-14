"""Endpoints de los movimientos recurrentes (ADR-0027).

Todos piden sesión y filtran por la persona: una regla ajena responde 404,
igual que una que no existe (ADR-0009). Los que cambian estado exigen el
encabezado CSRF.
"""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from rinde.shared.api.csrf import CSRF
from rinde.shared.api.identity import CurrentUserId
from rinde.shared.api.schemas import AmountIn, AmountOut, error_responses
from rinde.shared.domain.money import Currency
from rinde.transactions.api.installments import GeneratedResponse
from rinde.transactions.api.router import IdempotencyKey, Unit
from rinde.transactions.application.recurring import RuleChange, RuleInput, RuleView
from rinde.transactions.domain.category import TransactionKind
from rinde.transactions.domain.recurring import Frequency
from rinde.transactions.domain.transaction import Description

router = APIRouter(prefix="/recurring", tags=["recurring"])


class RecurringRuleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: UUID
    kind: TransactionKind
    amount: AmountIn
    category_id: UUID
    frequency: Frequency
    starts_on: date = Field(
        description="La primera vez: como mucho un año antes o un año después de hoy"
    )
    description: str | None = Field(default=None, max_length=Description.MAX_LENGTH)


class RecurringRuleChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: AmountIn = Field(description="Vale desde la próxima vez")
    description: str | None = Field(default=None, max_length=Description.MAX_LENGTH)


class RecurringRuleResponse(BaseModel):
    id: UUID
    account_id: UUID
    kind: TransactionKind
    amount: AmountOut
    currency: Currency
    category_id: UUID
    frequency: Frequency
    starts_on: date
    description: str | None
    created_at: datetime
    cancelled_at: datetime | None
    generated: int = Field(description="Cuántas veces ya se volvió movimiento, borradas incluidas")
    next_on: date | None = Field(description="La próxima vez que se genera; nada si se canceló")

    @classmethod
    def from_view(cls, view: RuleView) -> RecurringRuleResponse:
        rule = view.rule
        return cls(
            id=rule.id,
            account_id=rule.account_id,
            kind=rule.kind,
            amount=rule.money.amount,
            currency=rule.money.currency,
            category_id=rule.category_id,
            frequency=rule.frequency,
            starts_on=rule.starts_on,
            description=rule.description.value if rule.description else None,
            created_at=rule.created_at,
            cancelled_at=rule.cancelled_at,
            generated=view.generated,
            next_on=view.next.on if view.next else None,
        )


@router.get("", responses=error_responses(401), summary="Listar mis movimientos recurrentes")
async def list_rules(user_id: CurrentUserId, unit: Unit) -> list[RecurringRuleResponse]:
    """Primero las activas; después las canceladas."""
    return [
        RecurringRuleResponse.from_view(view) for view in await unit.list_rules.execute(user_id)
    ]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=CSRF,
    responses=error_responses(401, 403, 404, 409, 422),
    summary="Registrar un movimiento recurrente",
)
async def create_rule(
    payload: RecurringRuleRequest,
    user_id: CurrentUserId,
    unit: Unit,
    idempotency_key: IdempotencyKey = None,
) -> RecurringRuleResponse:
    """Lo que ya venció se vuelve movimiento en el mismo pedido."""
    view = await unit.create_rule.execute(
        user_id,
        RuleInput(
            account_id=payload.account_id,
            kind=payload.kind,
            amount=payload.amount,
            category_id=payload.category_id,
            frequency=payload.frequency,
            starts_on=payload.starts_on,
            description=payload.description,
        ),
        idempotency_key,
    )
    return RecurringRuleResponse.from_view(view)


@router.post(
    "/due",
    dependencies=CSRF,
    responses=error_responses(401, 403),
    summary="Generar los movimientos recurrentes vencidos",
)
async def generate_due(user_id: CurrentUserId, unit: Unit) -> GeneratedResponse:
    """Lo pide la app al abrirse, como las cuotas (ADR-0027). Repetirlo no duplica nada."""
    return GeneratedResponse(created=len(await unit.generate_due_recurring.execute(user_id)))


@router.patch(
    "/{rule_id}",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404, 409, 422),
    summary="Cambiar el monto de un movimiento recurrente",
)
async def change_rule(
    rule_id: UUID, payload: RecurringRuleChangeRequest, user_id: CurrentUserId, unit: Unit
) -> RecurringRuleResponse:
    """Antes de cambiarlo se genera lo vencido con el monto anterior."""
    view = await unit.change_rule.execute(
        user_id, rule_id, RuleChange(amount=payload.amount, description=payload.description)
    )
    return RecurringRuleResponse.from_view(view)


@router.post(
    "/{rule_id}/cancel",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404),
    summary="Cancelar un movimiento recurrente",
)
async def cancel_rule(rule_id: UUID, user_id: CurrentUserId, unit: Unit) -> RecurringRuleResponse:
    """Lo ya generado queda; no se genera más."""
    return RecurringRuleResponse.from_view(await unit.cancel_rule.execute(user_id, rule_id))
