import pytest

from rinde.health.application.check_readiness import CheckReadiness
from tests.fakes import FakeDatabaseProbe

pytestmark = pytest.mark.anyio


async def test_ready_when_database_is_reachable() -> None:
    probe = FakeDatabaseProbe(reachable=True)

    report = await CheckReadiness(probe).execute()

    assert report.ready
    assert report.database
    assert probe.calls == 1


async def test_not_ready_when_database_is_unreachable() -> None:
    report = await CheckReadiness(FakeDatabaseProbe(reachable=False)).execute()

    assert not report.ready
    assert not report.database
