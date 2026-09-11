from fastapi import status
from fastapi.testclient import TestClient

from rinde.config import Settings
from rinde.main import create_app
from tests.fakes import FakeDatabaseProbe


def _client(settings: Settings, *, database_reachable: bool = True) -> TestClient:
    probe = FakeDatabaseProbe(reachable=database_reachable)
    return TestClient(create_app(settings, database_probe=probe))


def test_live_returns_ok_and_running_version(settings: Settings) -> None:
    deployed = settings.model_copy(update={"version": "abc123"})

    with _client(deployed) as client:
        response = client.get("/api/health/live")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "version": "abc123"}


def test_health_endpoints_answer_head_requests(settings: Settings) -> None:
    with _client(settings) as client:
        assert client.head("/api/health/live").status_code == status.HTTP_200_OK
        assert client.head("/api/health/ready").status_code == status.HTTP_200_OK


def test_ready_returns_ok_when_database_is_reachable(settings: Settings) -> None:
    with _client(settings) as client:
        response = client.get("/api/health/ready")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "database": "ok"}


def test_ready_returns_503_when_database_is_unreachable(settings: Settings) -> None:
    with _client(settings, database_reachable=False) as client:
        response = client.get("/api/health/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"status": "unavailable", "database": "unavailable"}


def test_docs_are_published_outside_production(settings: Settings) -> None:
    with _client(settings) as client:
        assert client.get("/api/docs").status_code == status.HTTP_200_OK
        assert client.get("/api/openapi.json").status_code == status.HTTP_200_OK


def test_docs_are_hidden_in_production(settings: Settings) -> None:
    production = settings.model_copy(update={"environment": "production"})

    with _client(production) as client:
        assert client.get("/api/docs").status_code == status.HTTP_404_NOT_FOUND
        assert client.get("/api/openapi.json").status_code == status.HTTP_404_NOT_FOUND


def test_default_wiring_uses_real_database_probe(settings: Settings) -> None:
    """Sin reemplazos, la app arma su motor de base de datos y lo libera al cerrar."""
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health/live")

    assert response.status_code == status.HTTP_200_OK
