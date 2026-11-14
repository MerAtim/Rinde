"""La caché de la serie del IPC."""

from datetime import date, timedelta

import pytest

from rinde.inflation.application.ports import CpiSourceUnavailableError
from rinde.inflation.application.providers import CachedCpiProvider
from tests.fakes import FakeClock
from tests.unit.inflation.fakes import FakeCpiProvider, cpi

pytestmark = pytest.mark.anyio

TTL = timedelta(hours=1)


async def test_the_series_is_asked_once_per_while() -> None:
    inner = FakeCpiProvider(cpi(date(2026, 10, 1), "1"))
    clock = FakeClock()
    cached = CachedCpiProvider(inner, clock, ttl=TTL)

    first = await cached.series()
    second = await cached.series()
    clock.advance(TTL)
    third = await cached.series()

    assert first == second == third
    assert inner.calls == 2


async def test_an_error_is_not_kept() -> None:
    inner = FakeCpiProvider(cpi(date(2026, 10, 1), "1"), down=True)
    cached = CachedCpiProvider(inner, FakeClock(), ttl=TTL)

    with pytest.raises(CpiSourceUnavailableError):
        await cached.series()
    inner.down = False

    assert len(await cached.series()) == 1
    assert inner.calls == 2
