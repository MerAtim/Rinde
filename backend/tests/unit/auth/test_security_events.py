"""Qué evento de seguridad registra cada caso de uso de auth, sin datos de más (ADR-0035)."""

from datetime import timedelta
from uuid import UUID

import pytest

from rinde.auth.application.ports import ClientAction, SecurityDetail, SecurityEvent
from rinde.auth.application.rate_limits import MAX_REGISTRATIONS_PER_CLIENT
from rinde.auth.application.sessions import MAX_FAILED_ATTEMPTS
from rinde.auth.domain.errors import (
    InvalidCredentialsError,
    InvalidRecoveryCodeError,
    NotAuthenticatedError,
    TooManyAttemptsError,
)
from rinde.auth.infrastructure.security_log import CATALOG
from tests.fakes import InMemoryAuthUnitFactory, RecordedSecurityEvent

pytestmark = pytest.mark.anyio

PASSPHRASE = "mi gato come fideos los martes"
WRONG = "otra frase bastante larga"
NEW_PASSPHRASE = "una frase nueva y bien larga"
CLIENT = "203.0.113.7"


def _last(factory: InMemoryAuthUnitFactory) -> RecordedSecurityEvent:
    return factory.security_log.events[-1]


def test_every_event_has_a_level_and_a_description() -> None:
    assert set(CATALOG) == set(SecurityEvent)


async def test_login_records_success_and_failure_with_the_account_id() -> None:
    factory = InMemoryAuthUnitFactory()
    async with factory() as unit:
        user = (await unit.register.execute("mechi", PASSPHRASE)).user

        with pytest.raises(InvalidCredentialsError):
            await unit.login.execute("mechi", WRONG, CLIENT)
        assert _last(factory) == RecordedSecurityEvent(
            SecurityEvent.LOGIN_FAILED, (user.id,), CLIENT
        )

        await unit.login.execute("mechi", PASSPHRASE, CLIENT)
        assert _last(factory) == RecordedSecurityEvent(
            SecurityEvent.LOGIN_SUCCEEDED, (user.id,), CLIENT
        )


@pytest.mark.parametrize("username", ["nadie", "x"], ids=["no existe", "nombre inválido"])
async def test_a_failure_on_an_unknown_account_carries_no_id(username: str) -> None:
    factory = InMemoryAuthUnitFactory()
    async with factory() as unit:
        with pytest.raises(InvalidCredentialsError):
            await unit.login.execute(username, WRONG, CLIENT)

    assert factory.security_log.events == [
        RecordedSecurityEvent(SecurityEvent.LOGIN_FAILED, (), CLIENT)
    ]


async def test_a_locked_account_is_recorded_with_its_id_and_the_reason() -> None:
    factory = InMemoryAuthUnitFactory()
    async with factory() as unit:
        user = (await unit.register.execute("mechi", PASSPHRASE)).user
        for _ in range(MAX_FAILED_ATTEMPTS):
            with pytest.raises(InvalidCredentialsError):
                await unit.login.execute("mechi", WRONG, CLIENT)
        with pytest.raises(TooManyAttemptsError):
            await unit.login.execute("mechi", PASSPHRASE, CLIENT)

    assert _last(factory) == RecordedSecurityEvent(
        SecurityEvent.ACCOUNT_LOCKED, (user.id, SecurityDetail.MAX_RETRIES), CLIENT
    )


async def test_hitting_a_limit_per_origin_records_the_action_and_the_limit() -> None:
    factory = InMemoryAuthUnitFactory()
    async with factory() as unit:
        for number in range(MAX_REGISTRATIONS_PER_CLIENT):
            await unit.register.execute(f"persona{number}", PASSPHRASE, CLIENT)
        with pytest.raises(TooManyAttemptsError):
            await unit.register.execute("una_mas", PASSPHRASE, CLIENT)

    assert _last(factory) == RecordedSecurityEvent(
        SecurityEvent.RATE_LIMIT_EXCEEDED,
        (ClientAction.REGISTRATION, MAX_REGISTRATIONS_PER_CLIENT),
        CLIENT,
    )


async def test_registering_and_starting_a_demo_record_the_new_account() -> None:
    factory = InMemoryAuthUnitFactory()
    async with factory() as unit:
        user = (await unit.register.execute("mechi", PASSPHRASE, CLIENT)).user
        assert _last(factory) == RecordedSecurityEvent(
            SecurityEvent.USER_CREATED, (user.id,), CLIENT
        )

        await unit.start_demo.execute(CLIENT)

    demo = _last(factory)
    assert demo.event is SecurityEvent.USER_CREATED
    assert demo.params[1:] == (SecurityDetail.DEMO,)
    assert isinstance(demo.params[0], UUID)


async def test_recovery_records_the_change_or_the_wrong_code() -> None:
    factory = InMemoryAuthUnitFactory()
    async with factory() as unit:
        registration = await unit.register.execute("mechi", PASSPHRASE)
        user = registration.user

        # Un código con buena forma pero equivocado, y uno que ni tiene la forma.
        for wrong_code in ("ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZ", "AAAA"):
            with pytest.raises(InvalidRecoveryCodeError):
                await unit.recover.execute("mechi", wrong_code, NEW_PASSPHRASE, CLIENT)
            assert _last(factory) == RecordedSecurityEvent(
                SecurityEvent.PASSWORD_CHANGE_FAILED, (user.id,), CLIENT
            )

        await unit.recover.execute("mechi", registration.recovery_code, NEW_PASSPHRASE, CLIENT)
        assert _last(factory) == RecordedSecurityEvent(
            SecurityEvent.PASSWORD_CHANGED, (user.id,), CLIENT
        )


async def test_deleting_the_account_records_the_wrong_password_and_the_deletion() -> None:
    factory = InMemoryAuthUnitFactory()
    async with factory() as unit:
        user = (await unit.register.execute("mechi", PASSPHRASE)).user

        with pytest.raises(InvalidCredentialsError):
            await unit.delete_account.execute(user.id, WRONG, CLIENT)
        assert _last(factory) == RecordedSecurityEvent(
            SecurityEvent.REAUTHENTICATION_FAILED, (user.id,), CLIENT
        )

        await unit.delete_account.execute(user.id, PASSPHRASE, CLIENT)
        assert _last(factory) == RecordedSecurityEvent(
            SecurityEvent.USER_DELETED, (user.id, user.id), CLIENT
        )


async def test_logout_and_an_expired_session_are_recorded_once() -> None:
    factory = InMemoryAuthUnitFactory()
    async with factory() as unit:
        user = (await unit.register.execute("mechi", PASSPHRASE)).user
        token = await unit.login.execute("mechi", PASSPHRASE)

        await unit.logout.execute(token, CLIENT)
        assert _last(factory) == RecordedSecurityEvent(
            SecurityEvent.SESSION_ENDED, (user.id, SecurityDetail.LOGOUT), CLIENT
        )
        # Cerrar una sesión que ya no existe no registra nada nuevo.
        before = len(factory.security_log.events)
        await unit.logout.execute(token, CLIENT)
        assert len(factory.security_log.events) == before

        expiring = await unit.login.execute("mechi", PASSPHRASE)
        factory.clock.advance(timedelta(days=31))
        for _ in range(2):
            with pytest.raises(NotAuthenticatedError):
                await unit.authenticate.execute(expiring, CLIENT)

    expired = [
        event
        for event in factory.security_log.events
        if event.event is SecurityEvent.SESSION_USED_AFTER_EXPIRY
    ]
    assert expired == [
        RecordedSecurityEvent(SecurityEvent.SESSION_USED_AFTER_EXPIRY, (user.id,), CLIENT)
    ]


async def test_an_unknown_token_is_not_recorded() -> None:
    factory = InMemoryAuthUnitFactory()
    async with factory() as unit:
        with pytest.raises(NotAuthenticatedError):
            await unit.authenticate.execute("token-que-no-existe", CLIENT)

    assert factory.security_log.events == []


async def test_no_event_ever_carries_the_username_or_a_secret() -> None:
    """Un recorrido por todos los casos, mirando cada parámetro registrado."""
    factory = InMemoryAuthUnitFactory()
    async with factory() as unit:
        registration = await unit.register.execute("mechi", PASSPHRASE, CLIENT)
        with pytest.raises(InvalidCredentialsError):
            await unit.login.execute("mechi", WRONG, CLIENT)
        token = await unit.login.execute("mechi", PASSPHRASE, CLIENT)
        await unit.logout.execute(token, CLIENT)
        await unit.recover.execute("mechi", registration.recovery_code, NEW_PASSPHRASE, CLIENT)
        await unit.delete_account.execute(registration.user.id, NEW_PASSPHRASE, CLIENT)

    secrets = {"mechi", PASSPHRASE, WRONG, NEW_PASSPHRASE, token, registration.recovery_code}
    assert len(factory.security_log.events) >= 6
    for recorded in factory.security_log.events:
        for param in recorded.params:
            assert isinstance(param, UUID | ClientAction | SecurityDetail | int)
            assert str(param) not in secrets


async def test_a_recovery_with_an_invalid_username_is_recorded_without_an_id() -> None:
    factory = InMemoryAuthUnitFactory()
    async with factory() as unit:
        with pytest.raises(InvalidRecoveryCodeError):
            await unit.recover.execute("x", "ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZ", NEW_PASSPHRASE, CLIENT)

    assert factory.security_log.events == [
        RecordedSecurityEvent(SecurityEvent.PASSWORD_CHANGE_FAILED, (), CLIENT)
    ]
