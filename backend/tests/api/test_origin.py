"""Con el secreto de origen configurado, la API solo atiende a quien lo trae (ADR-0032)."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import SecretStr
from starlette.types import Receive, Scope, Send

from rinde.config import Settings
from rinde.main import create_app
from rinde.shared.api.origin import OriginSecretMiddleware
from tests.fakes import FakeDatabaseProbe

SECRET = "s" * 32
NEXT_SECRET = "n" * 32
HEADER = "X-Rinde-Origin"


def _client(settings: Settings, secrets: str = SECRET) -> TestClient:
    guarded = settings.model_copy(update={"origin_secret": SecretStr(secrets)})
    return TestClient(create_app(guarded, database_probe=FakeDatabaseProbe(reachable=True)))


@pytest.mark.parametrize(
    "headers",
    [{}, {HEADER: "inventado"}, {HEADER: SECRET[:-1]}, {HEADER: ""}],
    ids=["sin cabecera", "otro valor", "casi igual", "vacia"],
)
def test_without_the_secret_the_api_answers_403(
    settings: Settings, headers: dict[str, str]
) -> None:
    with _client(settings) as client:
        response = client.get("/api/auth/me", headers=headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"code": "ORIGIN_REJECTED"}


def test_with_the_secret_the_request_goes_through(settings: Settings) -> None:
    with _client(settings) as client:
        response = client.get("/api/auth/me", headers={HEADER: SECRET})

    # Pasó el control de origen y llegó al endpoint, que pide sesión.
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_a_route_that_does_not_exist_is_also_rejected(settings: Settings) -> None:
    with _client(settings) as client:
        response = client.get("/api/no-existe")

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_the_body_is_not_read_without_the_secret(settings: Settings) -> None:
    with _client(settings) as client:
        response = client.post("/api/auth/login", content=b"x" * 2_000_000)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("path", ["/api/health/live", "/api/health/ready"])
def test_health_checks_stay_open_for_render_and_the_deploy(settings: Settings, path: str) -> None:
    with _client(settings) as client:
        response = client.get(path)

    assert response.status_code == status.HTTP_200_OK


def test_during_a_rotation_both_secrets_are_accepted(settings: Settings) -> None:
    with _client(settings, f"{NEXT_SECRET},{SECRET}") as client:
        for secret in (SECRET, NEXT_SECRET):
            assert (
                client.get("/api/auth/me", headers={HEADER: secret}).status_code
                == status.HTTP_401_UNAUTHORIZED
            )


def test_without_the_secret_configured_there_is_no_origin_check(settings: Settings) -> None:
    with TestClient(
        create_app(settings, database_probe=FakeDatabaseProbe(reachable=True))
    ) as client:
        assert client.get("/api/auth/me").status_code == status.HTTP_401_UNAUTHORIZED


def test_production_does_not_build_the_app_without_the_secret(settings: Settings) -> None:
    production = settings.model_copy(update={"environment": "production", "origin_secret": None})

    with pytest.raises(RuntimeError, match="RINDE_ORIGIN_SECRET"):
        create_app(production, database_probe=FakeDatabaseProbe(reachable=True))


async def _app(scope: Scope, receive: Receive, send: Send) -> None:
    """Una aplicación ASGI que no hace nada: alcanza para armar el middleware."""


def test_the_middleware_needs_at_least_one_secret() -> None:
    with pytest.raises(ValueError, match="secreto"):
        OriginSecretMiddleware(_app, secrets=())
