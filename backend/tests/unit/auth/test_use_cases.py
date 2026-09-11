from datetime import timedelta

import pytest

from rinde.auth.application.sessions import hash_token
from rinde.auth.domain.errors import (
    InvalidCredentialsError,
    InvalidRecoveryCodeError,
    NotAuthenticatedError,
    TooManyAttemptsError,
)
from tests.fakes import InMemoryAuthUnitFactory

pytestmark = pytest.mark.anyio

PASSPHRASE = "mi gato come fideos los martes"
NEW_PASSPHRASE = "una frase nueva y bien larga"


async def test_login_spends_a_verification_even_if_the_account_does_not_exist() -> None:
    factory = InMemoryAuthUnitFactory()

    async with factory() as unit:
        with pytest.raises(InvalidCredentialsError):
            await unit.login.execute("nadie", PASSPHRASE)

    assert factory.hasher.verify_calls == 1


async def test_failed_attempts_lock_the_account_until_the_window_passes() -> None:
    factory = InMemoryAuthUnitFactory()

    async with factory() as unit:
        await unit.register.execute("mechi", PASSPHRASE)
        for _ in range(10):
            with pytest.raises(InvalidCredentialsError):
                await unit.login.execute("mechi", "otra frase bastante larga")
        with pytest.raises(TooManyAttemptsError):
            await unit.login.execute("mechi", PASSPHRASE)

        factory.clock.advance(timedelta(minutes=16))

        assert await unit.login.execute("mechi", PASSPHRASE)


async def test_login_upgrades_outdated_password_hashes() -> None:
    factory = InMemoryAuthUnitFactory()

    async with factory() as unit:
        registration = await unit.register.execute("mechi", PASSPHRASE)
        factory.hasher.version = 2
        await unit.login.execute("mechi", PASSPHRASE)

    assert factory.users.store[registration.user.id].password_hash.startswith("hash:v2:")


async def test_recovery_rotates_the_code_and_closes_every_session() -> None:
    factory = InMemoryAuthUnitFactory()

    async with factory() as unit:
        registration = await unit.register.execute("mechi", PASSPHRASE)
        recovery = await unit.recover.execute("mechi", registration.recovery_code, NEW_PASSPHRASE)

        assert recovery.recovery_code != registration.recovery_code
        assert hash_token(registration.session_token) not in factory.sessions.store
        with pytest.raises(InvalidRecoveryCodeError):
            await unit.recover.execute(
                "mechi", registration.recovery_code, "otra frase nueva y larga"
            )
        assert await unit.login.execute("mechi", NEW_PASSPHRASE)


async def test_expired_sessions_are_rejected_and_removed() -> None:
    factory = InMemoryAuthUnitFactory()

    async with factory() as unit:
        registration = await unit.register.execute("mechi", PASSPHRASE)
        factory.clock.advance(timedelta(days=31))
        with pytest.raises(NotAuthenticatedError):
            await unit.authenticate.execute(registration.session_token)

    assert factory.sessions.store == {}
