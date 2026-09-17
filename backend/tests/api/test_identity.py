"""La identidad del pedido que usan los módulos distintos de auth."""

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from rinde.config import Settings
from rinde.main import create_app
from rinde.shared.api.identity import CurrentUserId
from tests.fakes import FakeDatabaseProbe, InMemoryAuthUnitFactory

CSRF = {"X-Requested-With": "rinde"}


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    app = create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=InMemoryAuthUnitFactory(),
    )

    @app.get("/api/prueba/quien")
    async def quien(user_id: CurrentUserId) -> dict[str, str]:
        return {"user_id": str(user_id)}

    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def test_without_a_session_the_request_is_rejected(client: TestClient) -> None:
    response = client.get("/api/prueba/quien")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"code": "NOT_AUTHENTICATED"}


def test_with_a_session_the_module_gets_only_the_user_id(client: TestClient) -> None:
    client.post(
        "/api/auth/register",
        json={"username": "mechi", "password": "mi gato come fideos los martes"},
        headers=CSRF,
    )

    response = client.get("/api/prueba/quien")

    assert response.status_code == status.HTTP_200_OK
    UUID(response.json()["user_id"])


def test_a_closed_session_stops_identifying(client: TestClient) -> None:
    client.post(
        "/api/auth/register",
        json={"username": "mechi", "password": "mi gato come fideos los martes"},
        headers=CSRF,
    )
    client.post("/api/auth/logout", headers=CSRF)

    assert client.get("/api/prueba/quien").status_code == status.HTTP_401_UNAUTHORIZED
