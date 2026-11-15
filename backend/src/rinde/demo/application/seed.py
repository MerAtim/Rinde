"""Los datos de una demo: tres meses de una vida en Argentina (ADR-0028).

Todo es inventado: ningún monto ni descripción sale de un resumen real. Las
fechas se calculan desde hoy, así la demo siempre muestra el mes en curso y los
dos anteriores. Nada cae en el futuro: un movimiento no puede tener fecha futura.

El orden importa. Los presupuestos van antes que los gastos, así el gasto del
súper del mes cruza el 80 % de su tope y dispara una alerta, como pasaría de
verdad.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from uuid import UUID

from rinde.demo.application.ports import (
    AccountType,
    Clock,
    DemoWriter,
    Entry,
    EntryKind,
    PlanEntry,
    RuleEntry,
    TransferEntry,
)
from rinde.shared.domain.calendar import add_months, argentine_day
from rinde.shared.domain.money import Currency, Money

MONTHS = 3
CENT = Decimal("0.01")
# Los precios suben un poco cada mes, como en cualquier economía con inflación.
MONTHLY_INCREASE = Decimal("1.03")


@dataclass(frozen=True, slots=True)
class _Monthly:
    """Un gasto o ingreso que se repite cada mes, el mismo día, con su precio del primer mes."""

    day: int
    account: str
    kind: EntryKind
    category: str
    amount: str
    description: str


_EXPENSE = EntryKind.EXPENSE
_INCOME = EntryKind.INCOME

_EVERY_MONTH: tuple[_Monthly, ...] = (
    _Monthly(1, "bank", _INCOME, "sueldo", "2150000.00", "Sueldo"),
    _Monthly(2, "cash", _EXPENSE, "transporte", "15000.00", "Carga de la SUBE"),
    _Monthly(3, "bank", _EXPENSE, "supermercado", "96430.50", "Compra grande del mes"),
    _Monthly(5, "bank", _EXPENSE, "salud", "18750.00", "Farmacia"),
    _Monthly(6, "cash", _EXPENSE, "salidas", "24000.00", "Cine"),
    _Monthly(8, "bank", _EXPENSE, "servicios", "41200.00", "Luz"),
    _Monthly(10, "cash", _EXPENSE, "supermercado", "88120.00", "Verdulería y carnicería"),
    _Monthly(12, "bank", _EXPENSE, "servicios", "32990.00", "Internet"),
    _Monthly(14, "cash", _EXPENSE, "transporte", "15000.00", "Carga de la SUBE"),
    _Monthly(15, "bank", _EXPENSE, "servicios", "21500.00", "Celular"),
    _Monthly(17, "bank", _EXPENSE, "supermercado", "102760.30", "Supermercado"),
    _Monthly(20, "bank", _EXPENSE, "salidas", "68500.00", "Cena con amigos"),
    _Monthly(24, "bank", _EXPENSE, "supermercado", "91315.90", "Supermercado"),
)

# Topes del mes en curso. El del súper queda cerca del 90 %: se ve la alerta.
_BUDGETS: tuple[tuple[str, str], ...] = (
    ("supermercado", "420000.00"),
    ("salidas", "150000.00"),
    ("transporte", "60000.00"),
)


def _price(amount: str, month: int) -> Decimal:
    return (Decimal(amount) * MONTHLY_INCREASE**month).quantize(CENT, rounding=ROUND_HALF_EVEN)


class SeedDemo:
    """Implementa el puerto `DemoSeeder` de auth: llena una demo recién creada."""

    def __init__(self, writer: DemoWriter, clock: Clock) -> None:
        self._writer = writer
        self._clock = clock

    async def seed(self, owner_id: UUID) -> None:
        writer = self._writer
        today = argentine_day(self._clock.now())
        this_month = today.replace(day=1)
        first_month = add_months(this_month, -(MONTHS - 1))

        accounts = {
            "bank": await writer.open_account(
                owner_id, "Cuenta sueldo", AccountType.BANK, Currency.ARS
            ),
            "cash": await writer.open_account(owner_id, "Efectivo", AccountType.CASH, Currency.ARS),
            "usd": await writer.open_account(
                owner_id, "Ahorro en dólares", AccountType.BANK, Currency.USD
            ),
            "card": await writer.open_account(
                owner_id, "Tarjeta de crédito", AccountType.CREDIT_CARD, Currency.ARS
            ),
        }
        categories = await writer.categories(owner_id)

        for slug, limit in _BUDGETS:
            await writer.set_budget(owner_id, categories[slug], Money(Decimal(limit), Currency.ARS))

        # Lo que se genera solo: el alquiler y la prepaga, y una compra en cuotas.
        await writer.recurring(
            owner_id,
            RuleEntry(
                accounts["bank"],
                _EXPENSE,
                Decimal("680000.00"),
                categories["alquiler"],
                first_month.replace(day=10),
                "Alquiler del departamento",
            ),
        )
        await writer.recurring(
            owner_id,
            RuleEntry(
                accounts["bank"],
                _EXPENSE,
                Decimal("245000.00"),
                categories["salud"],
                first_month.replace(day=5),
                "Prepaga",
            ),
        )
        await writer.installments(
            owner_id,
            PlanEntry(
                accounts["card"],
                categories["otros"],
                Decimal("1350000.00"),
                6,
                first_month.replace(day=15),
                "Heladera",
            ),
        )

        for month in range(MONTHS):
            start = add_months(first_month, month)
            for item in _EVERY_MONTH:
                await writer.record(
                    owner_id,
                    Entry(
                        accounts[item.account],
                        item.kind,
                        _price(item.amount, month),
                        categories[item.category],
                        _day(start, item.day, today),
                        item.description,
                    ),
                )
            await writer.transfer(
                owner_id,
                TransferEntry(
                    accounts["bank"],
                    accounts["cash"],
                    Decimal("120000.00"),
                    Decimal("120000.00"),
                    _day(start, 2, today),
                    "Retiro del cajero",
                ),
            )

        # El mes anterior: un trabajo afuera cobrado en dólares, y pesos pasados a dólares.
        previous = add_months(this_month, -1)
        await writer.record(
            owner_id,
            Entry(
                accounts["usd"],
                _INCOME,
                Decimal("450.00"),
                categories["freelance"],
                previous.replace(day=18),
                "Diseño de un sitio para un cliente del exterior",
            ),
        )
        await writer.transfer(
            owner_id,
            TransferEntry(
                accounts["bank"],
                accounts["usd"],
                Decimal("1180000.00"),
                Decimal("800.00"),
                previous.replace(day=4),
                "Compra de dólares",
            ),
        )


# El último día que usa el calendario de la demo: cabe en cualquier mes.
LAST_DAY = 28


def _day(month_start: date, day: int, today: date) -> date:
    """El día del mes; en el mes en curso, el mismo orden comprimido hasta hoy.

    Correr a hoy todo lo que todavía no pasó apilaría la mitad del mes en un
    solo día. Comprimir mantiene el orden y la separación, y todo entra en el
    mes, así el súper sigue cruzando el 80 % de su tope.
    """
    if month_start != today.replace(day=1):
        return month_start.replace(day=day)
    return month_start.replace(day=1 + (day - 1) * (today.day - 1) // (LAST_DAY - 1))
