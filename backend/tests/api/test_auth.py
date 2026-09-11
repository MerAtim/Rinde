import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rinde.auth.application.sessions import hash_token
from rinde.config import Settings
from rinde.main import create_app
from tests.fakes import FakeDatabaseProbe, InMemoryAuthUnitFactory

CSRF = {"X-Requested-With": "rinde"}
PASSPHRASE = "mi gato come fideos los martes"
NEW_PASSPHRASE = "una frase nueva y bien larga"
COMPROMISED = "contraseña filtrada en 2019"
COOKIE = "__Host-rinde_session"


@pytest.fixture
def auth() -> InMemoryAuthUnitFactory:
    return InMemoryAuthUnitFactory(compromised={COMPROMISED})


@pytest.fixture
def client(settings: Settings, auth: InMemoryAuthUnitFactory) -> Iterator[TestClient]:
    app = create_app(settings, database_probe=FakeDatabaseProbe(reachable=True), auth_factory=auth)
    # HTTPS para que el cliente devuelva la cookie Secure, como hace el navegador.
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def _register(client: TestClient, username: str = "mechi", password: str = PASSPHRASE) -> Any:
    return client.post(
        "/api/auth/register", json={"username": username, "password": password}, headers=CSRF
    )


def _login(client: TestClient, password: str, username: str = "mechi") -> Any:
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}, headers=CSRF
    )


def test_register_creates_the_account_a_session_and_a_recovery_code(client: TestClient) -> None:
    response = _register(client)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["username"] == "mechi"
    assert re.fullmatch(r"[0-9A-Z]{4}(-[0-9A-Z]{4}){4}", body["recovery_code"])
    cookie = response.headers["set-cookie"].lower()
    for attribute in (f"{COOKIE.lower()}=", "httponly", "secure", "samesite=strict", "path=/"):
        assert attribute in cookie
    assert client.get("/api/auth/me").json() == {"username": "mechi"}


def test_actions_that_change_state_require_the_csrf_header(client: TestClient) -> None:
    response = client.post("/api/auth/register", json={"username": "mechi", "password": PASSPHRASE})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"code": "CSRF_REJECTED"}


@pytest.mark.parametrize(
    ("username", "password", "code"),
    [
        ("mechi", "corta pero no", "PASSWORD_TOO_SHORT"),
        ("mechi", "la cuenta de mechi es mía", "PASSWORD_CONTAINS_USERNAME"),
        ("mechi", COMPROMISED, "PASSWORD_COMPROMISED"),
        ("admin", PASSPHRASE, "USERNAME_RESERVED"),
        ("con espacio", PASSPHRASE, "USERNAME_INVALID"),
    ],
)
def test_register_rejects_invalid_data_with_stable_codes(
    client: TestClient, username: str, password: str, code: str
) -> None:
    response = _register(client, username, password)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {"code": code}


def test_register_rejects_a_taken_username(client: TestClient) -> None:
    _register(client)

    response = _register(client)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"code": "USERNAME_TAKEN"}


def test_me_requires_a_session(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"code": "NOT_AUTHENTICATED"}


def test_login_errors_do_not_reveal_whether_the_account_exists(client: TestClient) -> None:
    _register(client)
    client.cookies.clear()

    wrong_password = _login(client, "otra frase bastante larga")
    unknown_account = _login(client, PASSPHRASE, username="nadie")

    assert wrong_password.status_code == unknown_account.status_code == status.HTTP_401_UNAUTHORIZED
    assert wrong_password.json() == unknown_account.json() == {"code": "INVALID_CREDENTIALS"}


def test_login_with_valid_credentials_starts_a_session(client: TestClient) -> None:
    _register(client)
    client.cookies.clear()

    response = _login(client, PASSPHRASE)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert client.get("/api/auth/me").status_code == status.HTTP_200_OK


def test_repeated_failures_lock_the_account_temporarily(client: TestClient) -> None:
    _register(client)
    client.cookies.clear()
    for _ in range(10):
        _login(client, "otra frase bastante larga")

    response = _login(client, PASSPHRASE)

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.json() == {"code": "TOO_MANY_ATTEMPTS"}
    assert response.headers["retry-after"] == "900"


def test_logout_closes_the_session(client: TestClient, auth: InMemoryAuthUnitFactory) -> None:
    _register(client)

    response = client.post("/api/auth/logout", headers=CSRF)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert auth.sessions.store == {}
    assert client.get("/api/auth/me").status_code == status.HTTP_401_UNAUTHORIZED


def test_recovery_changes_the_password_rotates_the_code_and_closes_old_sessions(
    client: TestClient, auth: InMemoryAuthUnitFactory
) -> None:
    first_code = _register(client).json()["recovery_code"]
    old_token = client.cookies.get(COOKIE)

    response = client.post(
        "/api/auth/recover",
        json={
            "username": "mechi",
            "recovery_code": first_code.lower().replace("-", " "),
            "new_password": NEW_PASSPHRASE,
        },
        headers=CSRF,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["recovery_code"] != first_code
    assert old_token is not None
    assert hash_token(old_token) not in auth.sessions.store
    reuse = client.post(
        "/api/auth/recover",
        json={"username": "mechi", "recovery_code": first_code, "new_password": NEW_PASSPHRASE},
        headers=CSRF,
    )
    assert reuse.status_code == status.HTTP_401_UNAUTHORIZED
    assert reuse.json() == {"code": "RECOVERY_CODE_INVALID"}
