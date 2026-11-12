"""Esquemas de entrada y salida de alertas.

Los meses viajan como `AAAA-MM` y el dinero como string decimal (ADR-0002).
"""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from rinde.alerts.application.use_cases import FEED_SIZE, AlertFeed, AlertItem
from rinde.alerts.domain.alert import Threshold
from rinde.shared.api.schemas import MoneyResponse

MonthOut = Annotated[date, PlainSerializer(lambda value: f"{value:%Y-%m}", return_type=str)]


class AlertCategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str | None = Field(description="Solo en las sembradas: la interfaz las traduce")


class AlertResponse(BaseModel):
    id: UUID
    category: AlertCategoryResponse
    month: MonthOut = Field(description="El mes del presupuesto")
    threshold: Threshold = Field(description="warning al llegar al 80 %, over al 100 %")
    limit: MoneyResponse = Field(description="El tope cuando se disparó")
    spent: MoneyResponse = Field(description="Lo gastado cuando se disparó, en la moneda del tope")
    raised_at: datetime
    read: bool

    @classmethod
    def from_item(cls, item: AlertItem) -> AlertResponse:
        alert = item.alert
        return cls(
            id=alert.id,
            category=AlertCategoryResponse(
                id=item.category.id, name=item.category.name, slug=item.category.slug
            ),
            month=alert.month,
            threshold=alert.threshold,
            limit=MoneyResponse.from_money(alert.limit),
            spent=MoneyResponse.from_money(alert.spent),
            raised_at=alert.raised_at,
            read=alert.is_read,
        )


class AlertsResponse(BaseModel):
    unread: int = Field(description="Todas las sin leer, aunque no entren en la lista")
    alerts: list[AlertResponse] = Field(
        description=f"Las últimas {FEED_SIZE}, de la más nueva a la más vieja"
    )

    @classmethod
    def from_feed(cls, feed: AlertFeed) -> AlertsResponse:
        return cls(
            unread=feed.unread, alerts=[AlertResponse.from_item(item) for item in feed.items]
        )


class MarkReadRequest(BaseModel):
    """Las alertas que la persona vio. Las de otra persona se ignoran: no cambian."""

    model_config = ConfigDict(extra="forbid")

    ids: list[UUID] = Field(min_length=1, max_length=FEED_SIZE)
