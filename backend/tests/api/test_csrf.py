"""Candado de CSRF: ninguna ruta que cambie estado puede quedarse sin el encabezado.

El `dependencies=CSRF` se agrega a mano en cada endpoint (ADR-0007),
así que la defensa depende de que nadie se olvide. Este test recorre la
aplicación real en lugar de una lista escrita a mano: un endpoint nuevo que se
olvide de pedirlo falla acá y no llega a producción.
"""

import re
from collections.abc import Iterator

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from rinde.config import Settings
from rinde.main import create_app
from tests.fakes import FakeDatabaseProbe, InMemoryAuthUnitFactory

# Los métodos seguros no cambian estado, así que no necesitan el encabezado.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=InMemoryAuthUnitFactory(),
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def _state_changing_routes(app: FastAPI) -> list[tuple[str, str]]:
    """Cada (método, ruta) de la aplicación que puede cambiar estado.

    Se leen del esquema OpenAPI y no de `app.routes`, que la versión actual de
    FastAPI ya no entrega plano. El esquema es el contrato público del proyecto
    y la CI verifica que no se desvíe, así que un endpoint que no aparezca acá
    tampoco existe para el frontend.
    """
    routes: list[tuple[str, str]] = []
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            if method.upper() in SAFE_METHODS:
                continue
            # Los parámetros de ruta se reemplazan por un valor cualquiera: el
            # encabezado se verifica antes de resolver el recurso.
            routes.append((method.upper(), re.sub(r"\{[^}]+\}", "1", path)))
    return sorted(routes)


def test_every_state_changing_route_requires_the_csrf_header(
    app: FastAPI, client: TestClient
) -> None:
    routes = _state_changing_routes(app)
    assert routes, "No se descubrió ninguna ruta que cambie estado; revisar el descubrimiento"

    unlocked = [
        f"{method} {path}"
        for method, path in routes
        if client.request(method, path, json={}).status_code != status.HTTP_403_FORBIDDEN
    ]

    assert not unlocked, (
        "Estas rutas cambian estado y no rechazan la petición sin el encabezado CSRF. "
        "Falta agregarles dependencies=CSRF: " + ", ".join(unlocked)
    )


def test_the_csrf_header_has_to_carry_the_expected_value(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"username": "mechi", "password": "mi gato come fideos los martes"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"code": "CSRF_REJECTED"}
