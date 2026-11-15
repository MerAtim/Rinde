"""Los datos de la demo: nada en el futuro, nada apilado y una alerta a la vista (ADR-0028)."""

from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from rinde.demo.application.ports import (
    AccountType,
    Entry,
    EntryKind,
    PlanEntry,
    RuleEntry,
    TransferEntry,
)
from rinde.demo.application.seed import SeedDemo
from rinde.shared.domain.money import Currency, Money

pytestmark = pytest.mark.anyio

SLUGS = (
    "supermercado", "alquiler", "servicios", "transporte", "salidas", "salud", "otros",
    "sueldo", "freelance", "otros-ingresos",
)  # fmt: skip


class _Recorder:
    def __init__(self) -> None:
        self.categories_by_slug = {slug: uuid4() for slug in SLUGS}
        self.entries: list[Entry] = []
        self.transfers: list[TransferEntry] = []
        self.budgets: dict[UUID, Money] = {}

    async def open_account(
        self, owner_id: UUID, name: str, kind: AccountType, currency: Currency
    ) -> UUID:
        return uuid4()

    async def categories(self, owner_id: UUID) -> dict[str, UUID]:
        return self.categories_by_slug

    async def set_budget(self, owner_id: UUID, category_id: UUID, limit: Money) -> None:
        self.budgets[category_id] = limit

    async def record(self, owner_id: UUID, entry: Entry) -> None:
        self.entries.append(entry)

    async def transfer(self, owner_id: UUID, entry: TransferEntry) -> None:
        self.transfers.append(entry)

    async def installments(self, owner_id: UUID, entry: PlanEntry) -> None:
        pass

    async def recurring(self, owner_id: UUID, entry: RuleEntry) -> None:
        pass


class _Clock:
    def __init__(self, today: date) -> None:
        # Mediodía en Buenos Aires: el día argentino es el pedido.
        self._now = datetime(today.year, today.month, today.day, 15, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now


@pytest.mark.parametrize("today", [date(2026, 11, 2), date(2026, 11, 15), date(2026, 12, 31)])
async def test_nothing_is_in_the_future_nor_piled_on_one_day(today: date) -> None:
    writer = _Recorder()

    await SeedDemo(writer, _Clock(today)).seed(uuid4())

    dates = [entry.on for entry in writer.entries] + [item.on for item in writer.transfers]
    assert max(dates) <= today
    this_month = Counter(day for day in dates if day.replace(day=1) == today.replace(day=1))
    # Lo del mes se reparte entre el 1 y hoy; antes se corría todo a hoy.
    assert this_month[today] <= 3


@pytest.mark.parametrize("today", [date(2026, 11, 2), date(2026, 11, 15), date(2026, 12, 31)])
async def test_the_grocery_budget_shows_an_alert_any_day_of_the_month(today: date) -> None:
    writer = _Recorder()

    await SeedDemo(writer, _Clock(today)).seed(uuid4())

    groceries = writer.categories_by_slug["supermercado"]
    spent = sum(
        (
            entry.amount
            for entry in writer.entries
            if entry.category_id == groceries
            and entry.kind is EntryKind.EXPENSE
            and entry.on.replace(day=1) == today.replace(day=1)
        ),
        Decimal(0),
    )
    assert spent >= writer.budgets[groceries].amount * Decimal("0.8")
