"""El presupuesto: un tope de gasto mensual por categoría (ADR-0021).

Reglas:

* **Un tope vale desde un mes en adelante.** Crearlo, cambiarlo o quitarlo
  agrega una vigencia nueva desde el mes en curso, y nunca pisa las anteriores.
  Así octubre sigue mostrando el tope que tenía en octubre, aunque en noviembre
  se haya cambiado.
* **El sobrante no se acumula.** Cada mes se mide contra su tope, desde cero.
* **El tope tiene su propia moneda**, pesos o dólares. Un gasto en otra moneda
  se convierte con la cotización de su día, del lado prudente: como algo que se
  debe (ADR-0017). Lo que no se puede convertir no se suma: se informa aparte.
* **Un redondeo, al final**, con `ROUND_HALF_EVEN`. Lo restante es la resta de
  los dos números que se muestran, para que lo que se ve cierre exacto.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from rinde.budgets.domain.errors import (
    BudgetAmountInvalidError,
    BudgetCurrencyNotAllowedError,
    BudgetMonthInvalidError,
)
from rinde.shared.domain.money import Currency, Money

BUDGET_CURRENCIES = frozenset({Currency.ARS, Currency.USD})
"""Las que tienen cotización entre sí. Bitcoin, todavía no (ADR-0017)."""

WARNING_SHARE = Decimal("0.8")
"""Desde el 80 % del tope, el presupuesto avisa. Las alertas usan el mismo umbral."""

RATIO_QUANTUM = Decimal("0.0001")
"""La proporción con cuatro decimales: alcanza para un porcentaje con dos."""


def month_of(day: date) -> date:
    return day.replace(day=1)


def month_end(month: date) -> date:
    following = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    return following - timedelta(days=1)


@dataclass(frozen=True, slots=True)
class BudgetLimit:
    """Una vigencia: desde `since`, el tope de la categoría es `limit`.

    `limit` en `None` dice que desde ese mes la categoría ya no tiene tope.
    """

    id: UUID
    owner_id: UUID
    category_id: UUID
    since: date
    """El primer día del mes desde el que vale."""
    limit: Money | None
    recorded_at: datetime

    def __post_init__(self) -> None:
        if self.since.day != 1:
            raise BudgetMonthInvalidError
        if self.limit is None:
            return
        if self.limit.currency not in BUDGET_CURRENCIES:
            raise BudgetCurrencyNotAllowedError
        if not self.limit.is_positive:
            raise BudgetAmountInvalidError


def latest_in(history: Iterable[BudgetLimit], month: date) -> dict[UUID, BudgetLimit]:
    """La vigencia de cada categoría en un mes: la última que empezó hasta ese mes.

    Dos vigencias del mismo mes se desempatan por cuándo se registraron: gana la
    última. Incluye las que quitan el tope.
    """
    latest: dict[UUID, BudgetLimit] = {}
    for item in history:
        if item.since > month:
            continue
        current = latest.get(item.category_id)
        if current is None or (item.since, item.recorded_at) > (
            current.since,
            current.recorded_at,
        ):
            latest[item.category_id] = item
    return latest


def limits_in(history: Iterable[BudgetLimit], month: date) -> dict[UUID, BudgetLimit]:
    """Las categorías con tope en ese mes. La que lo quitó no aparece."""
    return {
        category_id: item
        for category_id, item in latest_in(history, month).items()
        if item.limit is not None
    }


class BudgetStatus(StrEnum):
    ON_TRACK = "on_track"
    WARNING = "warning"
    """Llegó al 80 % del tope."""
    OVER = "over"
    """Llegó al tope o lo pasó."""


@dataclass(frozen=True, slots=True)
class Expense:
    """Lo que se gastó un día en una categoría, en una moneda. Siempre positivo."""

    day: date
    money: Money


class Converter(Protocol):
    @property
    def target(self) -> Currency: ...

    def to_target(self, money: Money, day: date) -> Decimal | None:
        """Sin redondear. `None` si esa moneda o ese día no tienen cotización."""
        ...


@dataclass(frozen=True, slots=True)
class BudgetProgress:
    limit: Money
    spent: Money
    remaining: Money
    """Negativo cuando el gasto pasó el tope."""
    ratio: Decimal
    """Gastado sobre tope: 1 es el tope, y puede pasarlo."""
    status: BudgetStatus
    unconverted: list[Money]
    """Lo que no entró en `spent`, en su moneda: Bitcoin, o un día sin cotización."""

    @classmethod
    def measure(
        cls, limit: Money, expenses: Iterable[Expense], converter: Converter | None
    ) -> BudgetProgress:
        """`converter` lleva a la moneda del tope; sin él, solo cuenta lo que ya está en ella."""
        total = Decimal(0)
        left: dict[Currency, Decimal] = {}
        for expense in expenses:
            money = expense.money
            if money.currency is limit.currency:
                total += money.amount
                continue
            # Un gasto es algo que se debe: se convierte con el signo negativo (ADR-0017).
            value = None if converter is None else converter.to_target(-money, expense.day)
            if value is None:
                left[money.currency] = left.get(money.currency, Decimal(0)) + money.amount
                continue
            total -= value
        spent = Money.rounded(total, limit.currency)
        if spent >= limit:
            status = BudgetStatus.OVER
        elif spent.amount >= limit.amount * WARNING_SHARE:
            status = BudgetStatus.WARNING
        else:
            status = BudgetStatus.ON_TRACK
        return cls(
            limit=limit,
            spent=spent,
            remaining=limit - spent,
            ratio=(spent.amount / limit.amount).quantize(RATIO_QUANTUM, rounding=ROUND_HALF_EVEN),
            status=status,
            unconverted=[
                Money(amount.quantize(currency.quantum), currency)
                for currency, amount in sorted(left.items())
            ],
        )
