"""Casos de uso de alertas, con los otros módulos en memoria (ADR-0022)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from rinde.alerts.application.ports import BudgetReading, CategoryInfo, MonthReading
from rinde.alerts.application.unit import AlertsGateways, build_alerts_unit
from rinde.alerts.application.use_cases import FEED_SIZE
from rinde.alerts.domain.alert import BudgetAlert, Threshold
from rinde.shared.domain.money import Currency, Money
from tests.fakes import FakeClock, FakeTransaction
from tests.unit.alerts.fakes import FixedBudgets, FixedCategories, InMemoryAlertRepository

pytestmark = pytest.mark.anyio

OWNER = uuid4()
STRANGER = uuid4()
MONTH = date(2026, 11, 1)
# Las 12 de Buenos Aires del 10 de noviembre de 2026.
NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)
TODAY = date(2026, 11, 10)
MARKET = CategoryInfo(id=uuid4(), name="Supermercado", slug="groceries")
RENT = CategoryInfo(id=uuid4(), name="Alquiler", slug=None)


def ars(amount: str) -> Money:
    return Money(Decimal(amount), Currency.ARS)


def reading(category: CategoryInfo, spent: str, reached: Threshold | None) -> BudgetReading:
    return BudgetReading(category.id, ars("1000.00"), ars(spent), reached)


class Setup:
    def __init__(self) -> None:
        self.clock = FakeClock()
        self.clock.current = NOW
        self.alerts = InMemoryAlertRepository()
        self.db = FakeTransaction()
        self.budgets = FixedBudgets(OWNER, MonthReading(MONTH, []))
        self.unit = build_alerts_unit(
            self.alerts,
            self.db,
            AlertsGateways(budgets=self.budgets, categories=FixedCategories(OWNER, MARKET, RENT)),
            self.clock,
        )

    def month(self, *budgets: BudgetReading) -> None:
        self.budgets.reading = MonthReading(MONTH, list(budgets))


@pytest.fixture
def setup() -> Setup:
    return Setup()


async def test_reaching_80_percent_raises_a_warning_with_a_snapshot(setup: Setup) -> None:
    setup.month(reading(MARKET, "850.00", Threshold.WARNING), reading(RENT, "100.00", None))

    created = await setup.unit.evaluate.execute(OWNER, TODAY)

    assert created == [
        BudgetAlert(
            id=created[0].id,
            owner_id=OWNER,
            category_id=MARKET.id,
            month=MONTH,
            threshold=Threshold.WARNING,
            limit=ars("1000.00"),
            spent=ars("850.00"),
            raised_at=NOW,
        )
    ]
    assert setup.alerts.rows == created
    assert setup.db.commits == 1


async def test_evaluating_again_does_not_repeat_the_alert(setup: Setup) -> None:
    setup.month(reading(MARKET, "850.00", Threshold.WARNING))
    await setup.unit.evaluate.execute(OWNER, TODAY)

    setup.month(reading(MARKET, "900.00", Threshold.WARNING))
    assert await setup.unit.evaluate.execute(OWNER, TODAY) == []

    assert len(setup.alerts.rows) == 1
    # Sin nada nuevo, no hay nada que confirmar.
    assert setup.db.commits == 1


async def test_going_over_after_the_warning_raises_the_second_alert(setup: Setup) -> None:
    setup.month(reading(MARKET, "850.00", Threshold.WARNING))
    await setup.unit.evaluate.execute(OWNER, TODAY)

    setup.month(reading(MARKET, "1200.00", Threshold.OVER))
    [created] = await setup.unit.evaluate.execute(OWNER, TODAY)

    assert created.threshold is Threshold.OVER
    assert created.spent == ars("1200.00")


async def test_jumping_straight_over_raises_only_the_100_percent(setup: Setup) -> None:
    setup.month(reading(MARKET, "1200.00", Threshold.OVER))

    [created] = await setup.unit.evaluate.execute(OWNER, TODAY)
    # Un gasto que se borra lo deja en el 85 %: no avisa el 80 % después del 100 %.
    setup.month(reading(MARKET, "850.00", Threshold.WARNING))

    assert created.threshold is Threshold.OVER
    assert await setup.unit.evaluate.execute(OWNER, TODAY) == []


async def test_a_lost_alert_is_raised_by_the_next_expense(setup: Setup) -> None:
    """La evaluación mira el estado del mes, no el último gasto (ADR-0022)."""
    setup.month(reading(MARKET, "850.00", Threshold.WARNING))

    # Supermercado ya estaba en el 85 % y nadie lo evaluó: el proceso se cayó.
    # El próximo gasto del mes, de cualquier día y categoría, levanta el aviso.
    [created] = await setup.unit.evaluate.execute(OWNER, TODAY - timedelta(days=3))

    assert created.category_id == MARKET.id


async def test_an_expense_in_a_past_month_does_not_alert(setup: Setup) -> None:
    setup.month(reading(MARKET, "850.00", Threshold.WARNING))

    assert await setup.unit.evaluate.execute(OWNER, date(2026, 10, 31)) == []
    assert setup.budgets.calls == 0


async def test_the_month_is_the_argentine_one(setup: Setup) -> None:
    # Las 22 del 30 de noviembre en Buenos Aires: en UTC ya es diciembre.
    setup.clock.current = datetime(2026, 12, 1, 1, tzinfo=UTC)
    setup.month(reading(MARKET, "850.00", Threshold.WARNING))

    assert len(await setup.unit.evaluate.execute(OWNER, date(2026, 11, 30))) == 1


async def test_the_feed_shows_the_newest_first_with_the_unread_count(setup: Setup) -> None:
    setup.month(reading(MARKET, "850.00", Threshold.WARNING))
    [first] = await setup.unit.evaluate.execute(OWNER, TODAY)
    setup.clock.current = NOW + timedelta(hours=1)
    setup.month(
        reading(MARKET, "1200.00", Threshold.OVER), reading(RENT, "800.00", Threshold.WARNING)
    )
    await setup.unit.evaluate.execute(OWNER, TODAY)

    await setup.unit.mark_read.execute(OWNER, [first.id])
    feed = await setup.unit.list.execute(OWNER)

    assert feed.unread == 2
    # Las dos de la segunda evaluación tienen el mismo instante: las desempata el id.
    assert {(item.category.name, item.alert.threshold) for item in feed.items[:2]} == {
        ("Supermercado", Threshold.OVER),
        ("Alquiler", Threshold.WARNING),
    }
    assert feed.items[-1].alert.id == first.id
    assert feed.items[-1].alert.is_read
    assert all(not item.alert.is_read for item in feed.items[:-1])


async def test_the_feed_has_a_limit_but_the_count_does_not(setup: Setup) -> None:
    for index in range(FEED_SIZE + 5):
        setup.alerts.rows.append(
            BudgetAlert(
                id=uuid4(),
                owner_id=OWNER,
                category_id=MARKET.id,
                month=date(2020 + index // 12, index % 12 + 1, 1),
                threshold=Threshold.WARNING,
                limit=ars("1000.00"),
                spent=ars("850.00"),
                raised_at=NOW + timedelta(minutes=index),
            )
        )

    feed = await setup.unit.list.execute(OWNER)

    assert len(feed.items) == FEED_SIZE
    assert feed.unread == FEED_SIZE + 5


async def test_an_alert_of_a_deleted_category_is_not_shown(setup: Setup) -> None:
    orphan = CategoryInfo(id=uuid4(), name="Borrada", slug=None)
    setup.month(reading(orphan, "850.00", Threshold.WARNING))
    await setup.unit.evaluate.execute(OWNER, TODAY)

    feed = await setup.unit.list.execute(OWNER)

    assert feed.items == []


async def test_nobody_sees_or_reads_the_alerts_of_another_person(setup: Setup) -> None:
    setup.month(reading(MARKET, "850.00", Threshold.WARNING))
    [mine] = await setup.unit.evaluate.execute(OWNER, TODAY)

    await setup.unit.mark_read.execute(STRANGER, [mine.id])
    theirs = await setup.unit.list.execute(STRANGER)

    assert theirs.unread == 0
    assert theirs.items == []
    assert not setup.alerts.rows[0].is_read
    # El evento de otra persona tampoco le crea alertas al dueño.
    assert await setup.unit.evaluate.execute(STRANGER, TODAY) == []


async def test_marking_as_read_keeps_the_first_reading_time(setup: Setup) -> None:
    setup.month(reading(MARKET, "850.00", Threshold.WARNING))
    [alert] = await setup.unit.evaluate.execute(OWNER, TODAY)

    await setup.unit.mark_read.execute(OWNER, [alert.id])
    setup.clock.current = NOW + timedelta(days=1)
    await setup.unit.mark_read.execute(OWNER, [alert.id])

    assert setup.alerts.rows[0].read_at == NOW


async def test_marking_nothing_does_not_touch_the_database(setup: Setup) -> None:
    await setup.unit.mark_read.execute(OWNER, [])

    assert setup.db.commits == 0


async def test_an_alert_saved_by_a_concurrent_request_is_not_reported_again(
    setup: Setup,
) -> None:
    setup.month(reading(MARKET, "850.00", Threshold.WARNING))
    await setup.unit.evaluate.execute(OWNER, TODAY)

    async def nothing_raised(*_: object) -> dict[object, object]:
        # Lo que habría leído otro pedido antes de que se guardara la primera.
        return {}

    setup.alerts.raised_in = nothing_raised  # type: ignore[method-assign,assignment]
    commits = setup.db.commits

    assert await setup.unit.evaluate.execute(OWNER, TODAY) == []
    assert len(setup.alerts.rows) == 1
    assert setup.db.commits == commits
