"""Cuenta demo: una por visita, sin contraseña conocida, que vence sola (ADR-0028)."""

from datetime import timedelta

import pytest

from rinde.auth.application.demo import DEMO_TTL, MAX_DEMOS
from rinde.auth.application.rate_limits import MAX_DEMOS_PER_CLIENT
from rinde.auth.domain.errors import (
    DemoUnavailableError,
    InvalidCredentialsError,
    NotAuthenticatedError,
    TooManyAttemptsError,
    UsernameReservedError,
)
from tests.fakes import InMemoryAuthUnitFactory

pytestmark = pytest.mark.anyio

PASSPHRASE = "mi gato come fideos los martes"


async def test_a_demo_lasts_two_hours_and_nobody_can_log_in_to_it() -> None:
    factory = InMemoryAuthUnitFactory()

    async with factory() as unit:
        demo = await unit.create_demo.execute("203.0.113.7")
        token = await unit.start_demo_session.execute(demo.id)
        user = await unit.authenticate.execute(token)
        with pytest.raises(InvalidCredentialsError):
            await unit.login.execute(demo.username, "")

    assert demo.username.startswith("demo-")
    assert demo.expires_at == factory.clock.now() + DEMO_TTL
    assert user.demo_expires_at == demo.expires_at
    # La sesión vence con la demo, no a los 30 días de una cuenta común.
    assert [s.expires_at for s in factory.sessions.store.values()] == [demo.expires_at]
    assert factory.users.demo_locks == 1


async def test_an_expired_demo_does_not_open_and_is_purged_by_the_next_one() -> None:
    factory = InMemoryAuthUnitFactory()

    async with factory() as unit:
        old = await unit.create_demo.execute()
        token = await unit.start_demo_session.execute(old.id)
        factory.clock.advance(DEMO_TTL)

        with pytest.raises(NotAuthenticatedError):
            await unit.authenticate.execute(token)
        with pytest.raises(NotAuthenticatedError):
            await unit.start_demo_session.execute(old.id)
        new = await unit.create_demo.execute()

    assert list(factory.users.store) == [new.id]


async def test_the_demo_session_use_case_does_not_open_common_accounts() -> None:
    factory = InMemoryAuthUnitFactory()

    async with factory() as unit:
        registration = await unit.register.execute("mechi", PASSPHRASE)
        with pytest.raises(NotAuthenticatedError):
            await unit.start_demo_session.execute(registration.user.id)


async def test_nobody_can_register_a_name_that_looks_like_a_demo() -> None:
    factory = InMemoryAuthUnitFactory()

    async with factory() as unit:
        with pytest.raises(UsernameReservedError):
            await unit.register.execute("demo-mechi", PASSPHRASE)


async def test_one_client_creates_a_few_demos_per_hour() -> None:
    factory = InMemoryAuthUnitFactory()

    async with factory() as unit:
        for _ in range(MAX_DEMOS_PER_CLIENT):
            await unit.create_demo.execute("203.0.113.7")
        with pytest.raises(TooManyAttemptsError):
            await unit.create_demo.execute("203.0.113.7")
        # Otro origen no paga por el primero.
        assert await unit.create_demo.execute("198.51.100.4")


async def test_the_service_holds_at_most_a_fixed_number_of_demos() -> None:
    factory = InMemoryAuthUnitFactory()

    async with factory() as unit:
        for _ in range(MAX_DEMOS):
            await unit.create_demo.execute()
        with pytest.raises(DemoUnavailableError) as raised:
            await unit.create_demo.execute()

        # Cuando vencen las primeras, hay lugar otra vez.
        factory.clock.advance(DEMO_TTL + timedelta(seconds=1))
        await unit.create_demo.execute()

    assert raised.value.retry_after_seconds == int(DEMO_TTL.total_seconds())
    assert len(factory.users.store) == 1
