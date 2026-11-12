"""Esquemas de entrada y salida de presupuestos.

Los meses viajan como `AAAA-MM` y el dinero como string decimal (ADR-0002).
"""

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from rinde.budgets.application.use_cases import BudgetItem, BudgetMonth
from rinde.budgets.domain.budget import BudgetLimit, BudgetStatus
from rinde.shared.api.schemas import AmountIn, MoneyResponse, decimal_text
from rinde.shared.domain.money import Currency, Money
from rinde.shared.domain.rate_type import RateType

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"

MonthOut = Annotated[date, PlainSerializer(lambda value: f"{value:%Y-%m}", return_type=str)]
RatioOut = Annotated[Decimal, PlainSerializer(decimal_text, return_type=str)]


def parse_month(raw: str | None) -> date | None:
    """`AAAA-MM` ya validado por el patrón, como el primer día de ese mes."""
    if raw is None:
        return None
    year, month = raw.split("-")
    return date(int(year), int(month), 1)


class BudgetsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str | None = Field(
        default=None, pattern=MONTH_PATTERN, description="AAAA-MM. Si falta, el mes en curso"
    )


class BudgetRequest(BaseModel):
    """El tope entero, en su moneda: es reemplazarlo, no parchearlo."""

    model_config = ConfigDict(extra="forbid")

    amount: AmountIn
    currency: Currency

    def limit(self) -> Money:
        return Money(self.amount, self.currency)


class BudgetCategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str | None = Field(description="Solo en las sembradas: la interfaz las traduce")


class BudgetResponse(BaseModel):
    category: BudgetCategoryResponse
    since: MonthOut = Field(description="El mes desde el que vale este tope")
    limit: MoneyResponse
    spent: MoneyResponse = Field(description="En la moneda del tope, convertido día por día")
    remaining: MoneyResponse = Field(description="Negativo si el gasto pasó el tope")
    ratio: RatioOut = Field(description='Gastado sobre tope, como string: "1" es el tope')
    status: BudgetStatus = Field(description="on_track, warning desde el 80 %, over desde el 100 %")
    unconverted: list[MoneyResponse] = Field(
        description="Gastos que no entraron en `spent` porque no tienen cotización"
    )

    @classmethod
    def from_item(cls, item: BudgetItem) -> BudgetResponse:
        progress = item.progress
        return cls(
            category=BudgetCategoryResponse(
                id=item.category.id, name=item.category.name, slug=item.category.slug
            ),
            since=item.since,
            limit=MoneyResponse.from_money(progress.limit),
            spent=MoneyResponse.from_money(progress.spent),
            remaining=MoneyResponse.from_money(progress.remaining),
            ratio=progress.ratio,
            status=progress.status,
            unconverted=[MoneyResponse.from_money(money) for money in progress.unconverted],
        )


class BudgetsResponse(BaseModel):
    month: MonthOut
    rate_type: RateType = Field(description="El dólar con que se convierte otra moneda")
    budgets: list[BudgetResponse]

    @classmethod
    def from_month(cls, result: BudgetMonth) -> BudgetsResponse:
        return cls(
            month=result.month,
            rate_type=result.rate_type,
            budgets=[BudgetResponse.from_item(item) for item in result.items],
        )


class BudgetLimitResponse(BaseModel):
    category_id: UUID
    since: MonthOut
    limit: MoneyResponse

    @classmethod
    def from_limit(cls, vigency: BudgetLimit, limit: Money) -> BudgetLimitResponse:
        """`limit` es el pedido: la vigencia que vale tiene ese mismo tope."""
        return cls(
            category_id=vigency.category_id,
            since=vigency.since,
            limit=MoneyResponse.from_money(limit),
        )
