"""Las líneas del registro de seguridad que deja la API real (ADR-0035)."""

import json
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from fastapi import status
from fastapi.testclient import TestClient
from pydantic import SecretStr

from rinde.auth.infrastructure.security_log import LoggingSecurityLog
from rinde.config import Settings
from rinde.main import create_app
from tests.fakes import FakeDatabaseProbe, InMemoryAuthUnitFactory

Events = Callable[[], list[dict[str, Any]]]

CSRF = {"X-Requested-With": "rinde"}
VISITOR = "203.0.113.7"
PASSPHRASE = "mi gato come fideos los martes"


def _client(settings: Settings, auth: InMemoryAuthUnitFactory | None = None) -> TestClient:
    app = create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=auth or InMemoryAuthUnitFactory(),
    )
    return TestClient(app, base_url="https://testserver")


def test_a_failed_login_leaves_a_line_without_the_username_or_the_password(
    settings: Settings, security_events: Events
) -> None:
    auth = InMemoryAuthUnitFactory()
    # El adaptador de producción, en lugar del que solo anota en memoria.
    auth.services = replace(auth.services, security_log=LoggingSecurityLog())
    with _client(settings, auth) as client:
        client.post(
            "/api/auth/register",
            json={"username": "mechi", "password": PASSPHRASE},
            headers=CSRF,
        )
        response = client.post(
            "/api/auth/login",
            json={"username": "mechi", "password": "otra frase bastante larga"},
            headers={**CSRF, "CF-Connecting-IP": VISITOR},
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    [user_id] = list(auth.users.store)
    failure = security_events()[-1]
    assert failure == {
        "datetime": failure["datetime"],
        "appid": "rinde.api",
        "event": f"authn_login_fail:{user_id}",
        "level": "WARN",
        "description": "Inicio de sesión fallido",
        "source_ip": VISITOR,
    }
    written = json.dumps(security_events())
    assert "mechi" not in written
    assert "fideos" not in written
    assert "bastante larga" not in written


def test_a_request_without_the_csrf_header_is_recorded(
    settings: Settings, security_events: Events
) -> None:
    with _client(settings) as client:
        response = client.post(
            "/api/auth/logout?tracking=algo", headers={"CF-Connecting-IP": VISITOR}
        )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    [line] = security_events()
    assert line["event"] == "csrf_rejected"
    assert line["level"] == "WARN"
    assert line["source_ip"] == VISITOR
    assert line["request_method"] == "POST"
    # La ruta, sin la consulta: los parámetros pueden traer datos.
    assert line["request_uri"] == "/api/auth/logout"


def test_a_request_that_skips_the_worker_is_recorded_without_its_claimed_address(
    settings: Settings, security_events: Events
) -> None:
    guarded = settings.model_copy(update={"origin_secret": SecretStr("s" * 32)})
    with _client(guarded) as client:
        response = client.get("/api/auth/me", headers={"CF-Connecting-IP": VISITOR})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    [line] = security_events()
    assert line["event"] == "origin_rejected"
    assert line["request_method"] == "GET"
    assert line["request_uri"] == "/api/auth/me"
    assert "source_ip" not in line
