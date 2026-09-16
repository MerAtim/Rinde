"""Límites por dirección de origen.

El límite por cuenta no ve el rociado de contraseñas: una contraseña común
contra muchas cuentas deja a cada cuenta con un solo intento fallido. Estos
tests prueban justamente ese caso, que es el que el límite por cuenta deja pasar.
"""

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rinde.auth.application.rate_limits import (
    MAX_FAILURES_PER_CLIENT,
    MAX_REGISTRATIONS_PER_CLIENT,
    RETENTION,
)
from rinde.config import Settings
from rinde.main import create_app
from tests.fakes import FakeDatabaseProbe, InMemoryAuthUnitFactory

CSRF = {"X-Requested-With": "rinde"}
ATTACKER = {**CSRF, "CF-Connecting-IP": "203.0.113.7"}
SOMEONE_ELSE = {**CSRF, "CF-Connecting-IP": "198.51.100.4"}
PASSPHRASE = "mi gato come fideos los martes"


@pytest.fixture
def auth() -> InMemoryAuthUnitFactory:
    return InMemoryAuthUnitFactory()


@pytest.fixture
def client(settings: Settings, auth: InMemoryAuthUnitFactory) -> Iterator[TestClient]:
    app = create_app(settings, database_probe=FakeDatabaseProbe(reachable=True), auth_factory=auth)
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def _spray(client: TestClient, attempts: int, headers: dict[str, str]) -> Any:
    """Un intento contra cada cuenta: ninguna llega a su propio límite."""
    response = None
    for number in range(attempts):
        response = client.post(
            "/api/auth/login",
            json={"username": f"victima{number}", "password": "una frase cualquiera"},
            headers=headers,
        )
    return response


def test_spraying_from_one_client_is_blocked_even_with_a_different_account_each_time(
    client: TestClient, auth: InMemoryAuthUnitFactory
) -> None:
    last = _spray(client, MAX_FAILURES_PER_CLIENT, ATTACKER)
    assert last.status_code == status.HTTP_401_UNAUTHORIZED

    blocked = client.post(
        "/api/auth/login",
        json={"username": "una-mas", "password": "una frase cualquiera"},
        headers=ATTACKER,
    )

    assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert blocked.json() == {"code": "TOO_MANY_ATTEMPTS"}
    # Ninguna cuenta llegó a su propio límite: por eso hacía falta este.
    assert (
        max(
            sum(1 for who, _ in auth.failed_attempts.attempts if who == username)
            for username, _ in auth.failed_attempts.attempts
        )
        == 1
    )


def test_the_limit_follows_the_client_and_not_the_whole_service(client: TestClient) -> None:
    _spray(client, MAX_FAILURES_PER_CLIENT, ATTACKER)

    innocent = client.post(
        "/api/auth/login",
        json={"username": "mechi", "password": "una frase cualquiera"},
        headers=SOMEONE_ELSE,
    )

    assert innocent.status_code == status.HTTP_401_UNAUTHORIZED


def test_creating_accounts_in_bulk_from_one_client_is_blocked(client: TestClient) -> None:
    for number in range(MAX_REGISTRATIONS_PER_CLIENT):
        created = client.post(
            "/api/auth/register",
            json={"username": f"cuenta{number}", "password": PASSPHRASE},
            headers=ATTACKER,
        )
        assert created.status_code == status.HTTP_201_CREATED

    blocked = client.post(
        "/api/auth/register",
        json={"username": "una-mas", "password": PASSPHRASE},
        headers=ATTACKER,
    )

    assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert blocked.json() == {"code": "TOO_MANY_ATTEMPTS"}


def test_the_limit_expires_and_the_old_rows_are_cleaned_up(
    client: TestClient, auth: InMemoryAuthUnitFactory
) -> None:
    _spray(client, MAX_FAILURES_PER_CLIENT, ATTACKER)
    assert len(auth.client_activity.events) == MAX_FAILURES_PER_CLIENT

    auth.clock.advance(RETENTION + timedelta(minutes=1))
    allowed = client.post(
        "/api/auth/login",
        json={"username": "mechi", "password": "una frase cualquiera"},
        headers=ATTACKER,
    )

    assert allowed.status_code == status.HTTP_401_UNAUTHORIZED
    # La limpieza corre en cada escritura: no quedan filas vencidas acumulándose.
    assert len(auth.client_activity.events) == 1
    assert len(auth.failed_attempts.attempts) == 1
