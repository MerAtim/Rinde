"""Esquemas de entrada y salida del dashboard.

Los meses viajan como `AAAA-MM` y el dinero como string decimal (ADR-0002).
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from rinde.dashboard.application.use_cases import Dashboard
from rinde.dashboard.domain.report import CategoryRef
from rinde.shared.api.schemas import MoneyResponse
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
# Más que todas las cuentas que alguien razonable tiene: acota la consulta.
MAX_ACCOUNTS = 50

MonthOut = Annotated[date, PlainSerializer(lambda value: f"{value:%Y-%m}", return_type=str)]


def parse_month(raw: str | None) -> date | None:
    """`AAAA-MM` ya validado por el patrón, como el primer día de ese mes."""
    if raw is None:
        return None
    year, month = raw.split("-")
    return date(int(year), int(month), 1)


class DashboardQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=False)

    first: str | None = Field(
        default=None,
        alias="from",
        pattern=MONTH_PATTERN,
        description="Primer mes, AAAA-MM. Si falta, cinco meses antes del último",
    )
    last: str | None = Field(
        default=None,
        alias="to",
        pattern=MONTH_PATTERN,
        description="Último mes, AAAA-MM. Si falta, el mes en curso",
    )
    account: list[UUID] = Field(
        default_factory=list,
        max_length=MAX_ACCOUNTS,
        description="Cuentas a incluir; se repite el parámetro. Si falta, todas",
    )


class PeriodResponse(BaseModel):
    first: MonthOut
    last: MonthOut
    since: date
    until: date = Field(description="Último día incluido: fin del último mes, u hoy")


class ReferenceResponse(BaseModel):
    currency: Currency
    rate_type: RateType


class DashboardCategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str | None = Field(description="Solo en las sembradas: la interfaz las traduce")

    @classmethod
    def from_category(cls, category: CategoryRef) -> DashboardCategoryResponse:
        return cls(id=category.id, name=category.name, slug=category.slug)


class CategorySpendingResponse(BaseModel):
    category: DashboardCategoryResponse
    total: MoneyResponse


class MonthFlowResponse(BaseModel):
    month: MonthOut
    income: MoneyResponse
    expense: MoneyResponse
    net: MoneyResponse


class NetWorthPointResponse(BaseModel):
    month: MonthOut
    on: date = Field(description="Día del cierre: fin de mes, u hoy en el mes en curso")
    total: MoneyResponse | None = Field(
        description="Vacío si alguna cuenta no tuvo cotización ese día: no se inventa"
    )


class UnconvertedResponse(BaseModel):
    """Lo que quedó afuera de los totales, en su propia moneda."""

    currency: Currency
    income: MoneyResponse
    expense: MoneyResponse
    balance: MoneyResponse


class DashboardResponse(BaseModel):
    period: PeriodResponse
    reference: ReferenceResponse
    spending: list[CategorySpendingResponse] = Field(description="De mayor a menor")
    monthly: list[MonthFlowResponse] = Field(description="Un elemento por mes, sin huecos")
    net_worth: list[NetWorthPointResponse] = Field(
        description="Un cierre por mes; el último es el patrimonio de hoy"
    )
    unconverted: list[UnconvertedResponse]

    @classmethod
    def from_dashboard(cls, dashboard: Dashboard) -> DashboardResponse:
        period, report = dashboard.period, dashboard.report
        return cls(
            period=PeriodResponse(
                first=period.first, last=period.last, since=period.since, until=period.until
            ),
            reference=ReferenceResponse(
                currency=dashboard.reference.currency, rate_type=dashboard.reference.rate_type
            ),
            spending=[
                CategorySpendingResponse(
                    category=DashboardCategoryResponse.from_category(item.category),
                    total=MoneyResponse.from_money(item.total),
                )
                for item in report.spending
            ],
            monthly=[
                MonthFlowResponse(
                    month=item.month,
                    income=MoneyResponse.from_money(item.income),
                    expense=MoneyResponse.from_money(item.expense),
                    net=MoneyResponse.from_money(item.net),
                )
                for item in report.monthly
            ],
            net_worth=[
                NetWorthPointResponse(
                    month=point.month,
                    on=point.on,
                    total=None if point.total is None else MoneyResponse.from_money(point.total),
                )
                for point in report.net_worth
            ],
            unconverted=[
                UnconvertedResponse(
                    currency=item.currency,
                    income=MoneyResponse.from_money(item.income),
                    expense=MoneyResponse.from_money(item.expense),
                    balance=MoneyResponse.from_money(item.balance),
                )
                for item in report.unconverted
            ],
        )
