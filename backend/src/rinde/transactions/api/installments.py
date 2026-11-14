"""Endpoints de las compras en cuotas (ADR-0026).

Todos piden sesión y filtran por la persona: un plan ajeno responde 404, igual
que uno que no existe (ADR-0009). Los que cambian estado exigen el encabezado
CSRF.
"""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from rinde.shared.api.csrf import CSRF
from rinde.shared.api.identity import CurrentUserId
from rinde.shared.api.schemas import AmountIn, AmountOut, error_responses
from rinde.shared.domain.money import Currency
from rinde.transactions.api.router import IdempotencyKey, Unit
from rinde.transactions.application.installments import PlanInput, PlanView
from rinde.transactions.domain.installments import InstallmentPlan
from rinde.transactions.domain.transaction import Description

router = APIRouter(prefix="/installments", tags=["installments"])


class InstallmentPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: UUID
    category_id: UUID
    total: AmountIn = Field(description="Lo que se paga en total, con interés o sin él")
    count: int = Field(ge=InstallmentPlan.MIN_COUNT, le=InstallmentPlan.MAX_COUNT)
    first_on: date = Field(description="El día de la compra: el de la primera cuota")
    description: str | None = Field(default=None, max_length=Description.MAX_LENGTH)


class ScheduledInstallmentResponse(BaseModel):
    number: int
    due_on: date
    amount: AmountOut
    transaction_id: UUID | None = Field(description="El movimiento de la cuota, si ya se generó")
    deleted: bool = Field(description="La cuota se generó y después se borró")


class InstallmentPlanResponse(BaseModel):
    id: UUID
    account_id: UUID
    category_id: UUID
    total: AmountOut
    currency: Currency
    count: int
    first_on: date
    description: str | None
    created_at: datetime
    cancelled_at: datetime | None
    pending: AmountOut = Field(description="Lo que falta pagar: cero si se canceló")
    installments: list[ScheduledInstallmentResponse] = Field(description="Todas, en orden")

    @classmethod
    def from_view(cls, view: PlanView) -> InstallmentPlanResponse:
        plan = view.plan
        return cls(
            id=plan.id,
            account_id=plan.account_id,
            category_id=plan.category_id,
            total=plan.total.amount,
            currency=plan.total.currency,
            count=plan.count,
            first_on=plan.first_on,
            description=plan.description.value if plan.description else None,
            created_at=plan.created_at,
            cancelled_at=plan.cancelled_at,
            pending=view.pending.amount,
            installments=[
                ScheduledInstallmentResponse(
                    number=item.number,
                    due_on=item.due_on,
                    amount=item.money.amount,
                    transaction_id=item.generated.transaction_id if item.generated else None,
                    deleted=item.generated.is_deleted if item.generated else False,
                )
                for item in view.installments
            ],
        )


class GeneratedResponse(BaseModel):
    created: int = Field(description="Cuántas cuotas vencidas se volvieron movimientos")


@router.get("", responses=error_responses(401), summary="Listar mis compras en cuotas")
async def list_plans(user_id: CurrentUserId, unit: Unit) -> list[InstallmentPlanResponse]:
    return [
        InstallmentPlanResponse.from_view(view) for view in await unit.list_plans.execute(user_id)
    ]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=CSRF,
    responses=error_responses(401, 403, 404, 409, 422),
    summary="Registrar una compra en cuotas",
)
async def create_plan(
    payload: InstallmentPlanRequest,
    user_id: CurrentUserId,
    unit: Unit,
    idempotency_key: IdempotencyKey = None,
) -> InstallmentPlanResponse:
    """Las cuotas que ya vencieron se vuelven movimientos en el mismo pedido."""
    view = await unit.create_plan.execute(
        user_id,
        PlanInput(
            account_id=payload.account_id,
            category_id=payload.category_id,
            total=payload.total,
            count=payload.count,
            first_on=payload.first_on,
            description=payload.description,
        ),
        idempotency_key,
    )
    return InstallmentPlanResponse.from_view(view)


@router.post(
    "/due",
    dependencies=CSRF,
    responses=error_responses(401, 403),
    summary="Generar las cuotas vencidas",
)
async def generate_due(user_id: CurrentUserId, unit: Unit) -> GeneratedResponse:
    """Lo pide la pantalla al abrirse: no hay tareas programadas (ADR-0026).

    Repetirlo no duplica nada.
    """
    return GeneratedResponse(created=len(await unit.generate_due.execute(user_id)))


@router.post(
    "/{plan_id}/cancel",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404),
    summary="Cancelar una compra en cuotas",
)
async def cancel_plan(plan_id: UUID, user_id: CurrentUserId, unit: Unit) -> InstallmentPlanResponse:
    """Las cuotas ya generadas quedan; no se generan más."""
    return InstallmentPlanResponse.from_view(await unit.cancel_plan.execute(user_id, plan_id))
