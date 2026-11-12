"""El bus de eventos en el proceso (ADR-0022)."""

import logging
from dataclasses import dataclass

import pytest

from rinde.shared.infrastructure.events import InProcessEventBus

pytestmark = pytest.mark.anyio


@dataclass(frozen=True)
class Happened:
    value: int


@dataclass(frozen=True)
class Other:
    value: int


async def test_each_subscriber_gets_its_event_type_in_order() -> None:
    bus = InProcessEventBus()
    seen: list[str] = []

    async def first(event: Happened) -> None:
        seen.append(f"primero {event.value}")

    async def second(event: Happened) -> None:
        seen.append(f"segundo {event.value}")

    async def other(event: Other) -> None:
        seen.append(f"otro {event.value}")

    bus.subscribe(Happened, first)
    bus.subscribe(Happened, second)
    bus.subscribe(Other, other)

    await bus.publish(Happened(1))

    assert seen == ["primero 1", "segundo 1"]


async def test_an_event_without_subscribers_is_fine() -> None:
    await InProcessEventBus().publish(Happened(1))


async def test_a_failing_subscriber_is_logged_and_does_not_stop_the_rest(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bus = InProcessEventBus()
    seen: list[int] = []

    async def broken(_: Happened) -> None:
        raise RuntimeError("sin cotización")

    async def working(event: Happened) -> None:
        seen.append(event.value)

    bus.subscribe(Happened, broken)
    bus.subscribe(Happened, working)

    with caplog.at_level(logging.ERROR, logger="rinde.shared.infrastructure.events"):
        await bus.publish(Happened(7))

    assert seen == [7]
    [record] = caplog.records
    assert record.getMessage() == "Falló un suscriptor de eventos"
    assert record.__dict__["event"] == "Happened"
    assert "broken" in record.__dict__["handler"]
    assert record.exc_info is not None
