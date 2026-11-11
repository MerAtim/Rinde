"""Las cuentas del dashboard: qué se gastó en qué, cuánto entró y salió cada mes y
cuánto vale todo lo que tenés (ADR-0018).

Es Python puro sobre datos ya sumados por la base. La conversión llega desde
afuera como un `Converter`: acá no se sabe de dónde salen las cotizaciones.

Reglas:

* **Cada monto con la cotización de su día** (ADR-0017). Un gasto de marzo se
  convierte con la de marzo, aunque se mire en noviembre.
* **Del lado prudente** (ADR-0017). Un ingreso se convierte como algo que se
  tiene y un gasto como algo que se debe: nunca se valúa de más lo que entra ni
  de menos lo que sale. El patrimonio, con el signo del saldo de cada cuenta.
* **Un redondeo por número que se muestra**, al final, con `ROUND_HALF_EVEN`.
  Las conversiones se suman sin redondear. El neto de cada mes es la resta de
  los dos números redondeados, para que lo que se ve cierre exacto.
* **Nada inventado.** Lo que no se puede convertir (Bitcoin, o un día sin
  cotización) no entra en los totales y se informa aparte, en su moneda. Un
  cierre de mes con una cuenta sin cotización no tiene total.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from rinde.dashboard.domain.period import Period
from rinde.shared.domain.money import Currency, Money


class FlowKind(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


@dataclass(frozen=True, slots=True)
class CategoryRef:
    id: UUID
    name: str
    slug: str | None
    """Solo en las sembradas: la interfaz las traduce por este identificador (ADR-0011)."""


@dataclass(frozen=True, slots=True)
class Flow:
    """Lo que entró o salió un día en una categoría. Las transferencias no son flujos."""

    day: date
    kind: FlowKind
    category: CategoryRef
    money: Money
    """Siempre positivo: el sentido lo da `kind`."""


@dataclass(frozen=True, slots=True)
class BalanceChange:
    """Cuánto cambió el saldo de una cuenta en un mes. `month` en `None` es la apertura."""

    account_id: UUID
    month: date | None
    """El primer día del mes: el cierre de ese mes ya incluye el cambio."""
    change: Money


class Converter(Protocol):
    @property
    def target(self) -> Currency: ...

    def supports(self, currency: Currency) -> bool:
        """Si esa moneda tiene cotización hacia la de destino."""
        ...

    def to_target(self, money: Money, day: date) -> Decimal | None:
        """Sin redondear. `None` si ese día no tiene cotización."""
        ...


@dataclass(frozen=True, slots=True)
class CategoryTotal:
    category: CategoryRef
    total: Money


@dataclass(frozen=True, slots=True)
class MonthFlow:
    month: date
    income: Money
    expense: Money
    net: Money


@dataclass(frozen=True, slots=True)
class NetWorthPoint:
    month: date
    on: date
    """El día del cierre: fin de mes, u hoy en el mes en curso."""
    total: Money | None
    """`None` si alguna cuenta no tuvo cotización ese día: no se muestra un total incompleto."""


@dataclass(frozen=True, slots=True)
class Unconverted:
    """Lo que quedó afuera de los totales, en su propia moneda."""

    currency: Currency
    income: Money
    expense: Money
    balance: Money
    """El saldo de hoy de las cuentas en esa moneda que no se pudieron valuar."""


@dataclass(frozen=True, slots=True)
class Report:
    spending: list[CategoryTotal]
    monthly: list[MonthFlow]
    net_worth: list[NetWorthPoint]
    unconverted: list[Unconverted]


@dataclass
class _Left:
    income: Decimal = Decimal(0)
    expense: Decimal = Decimal(0)
    balance: Decimal = Decimal(0)

    @property
    def is_empty(self) -> bool:
        return not (self.income or self.expense or self.balance)


def build_report(
    period: Period,
    flows: list[Flow],
    changes: list[BalanceChange],
    converter: Converter,
) -> Report:
    left: defaultdict[Currency, _Left] = defaultdict(_Left)
    spending, monthly = _flows(period, flows, converter, left)
    net_worth = _net_worth(period, changes, converter, left)
    unconverted = [
        Unconverted(
            currency=currency,
            income=_exact(totals.income, currency),
            expense=_exact(totals.expense, currency),
            balance=_exact(totals.balance, currency),
        )
        for currency, totals in sorted(left.items())
        if not totals.is_empty
    ]
    return Report(spending, monthly, net_worth, unconverted)


def _exact(amount: Decimal, currency: Currency) -> Money:
    """Una suma de montos de la misma moneda: no hay nada que redondear, solo la escala."""
    return Money(amount.quantize(currency.quantum), currency)


def _flows(
    period: Period,
    flows: list[Flow],
    converter: Converter,
    left: defaultdict[Currency, _Left],
) -> tuple[list[CategoryTotal], list[MonthFlow]]:
    target = converter.target
    by_category: dict[UUID, tuple[CategoryRef, Decimal]] = {}
    income: defaultdict[date, Decimal] = defaultdict(Decimal)
    expense: defaultdict[date, Decimal] = defaultdict(Decimal)
    for flow in flows:
        is_income = flow.kind is FlowKind.INCOME
        # Un ingreso es algo que se tiene; un gasto, algo que se debe (ADR-0017).
        value = converter.to_target(flow.money if is_income else -flow.money, flow.day)
        if value is None:
            if is_income:
                left[flow.money.currency].income += flow.money.amount
            else:
                left[flow.money.currency].expense += flow.money.amount
            continue
        month = flow.day.replace(day=1)
        if is_income:
            income[month] += value
            continue
        expense[month] -= value
        category, total = by_category.get(flow.category.id, (flow.category, Decimal(0)))
        by_category[flow.category.id] = (category, total - value)

    spending = sorted(
        (
            CategoryTotal(category, Money.rounded(total, target))
            for category, total in by_category.values()
        ),
        key=lambda item: (-item.total.amount, item.category.name.casefold()),
    )
    monthly = []
    for month in period.months:
        month_income = Money.rounded(income[month], target)
        month_expense = Money.rounded(expense[month], target)
        monthly.append(MonthFlow(month, month_income, month_expense, month_income - month_expense))
    return spending, monthly


def _net_worth(
    period: Period,
    changes: list[BalanceChange],
    converter: Converter,
    left: defaultdict[Currency, _Left],
) -> list[NetWorthPoint]:
    balances: dict[UUID, Money] = {}
    dated: list[BalanceChange] = []
    for change in changes:
        if change.month is None:
            _apply(balances, change)
        else:
            dated.append(change)
    dated.sort(key=lambda change: change.month or period.since)

    points = []
    index = 0
    months = period.months
    for position, month in enumerate(months):
        on = period.closing(month)
        while index < len(dated) and (dated[index].month or on) <= on:
            _apply(balances, dated[index])
            index += 1
        is_current = position == len(months) - 1
        points.append(NetWorthPoint(month, on, _value(balances, on, converter, left, is_current)))
    return points


def _apply(balances: dict[UUID, Money], change: BalanceChange) -> None:
    current = balances.get(change.account_id)
    balances[change.account_id] = change.change if current is None else current + change.change


def _value(
    balances: dict[UUID, Money],
    on: date,
    converter: Converter,
    left: defaultdict[Currency, _Left],
    is_current: bool,
) -> Money | None:
    total: Decimal | None = Decimal(0)
    for balance in balances.values():
        if balance.is_zero:
            continue
        if not converter.supports(balance.currency):
            # Se informa una sola vez, con el saldo del último cierre: el de hoy.
            if is_current:
                left[balance.currency].balance += balance.amount
            continue
        value = converter.to_target(balance, on)
        # Sin cotización ese día, el cierre no tiene total; se sigue recorriendo
        # igual, para no dejar de informar lo que no se puede convertir.
        total = None if value is None or total is None else total + value
    return None if total is None else Money.rounded(total, converter.target)
