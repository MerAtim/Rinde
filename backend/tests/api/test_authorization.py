"""Candado de autorización por dueño en toda la API (ADR-0009).

Dos reglas, verificadas sobre las rutas del esquema OpenAPI y no sobre una lista
escrita a mano, igual que el candado de CSRF:

1. Sin sesión, toda ruta que no sea pública responde 401.
2. Con la sesión de otra persona, toda ruta con un identificador en el camino
   responde 404, igual que si el recurso no existiera (OWASP API1:2023). Un 403
   confirmaría que ese identificador existe.

Una ruta nueva con un parámetro de camino hace fallar estos tests hasta que se
registre acá cómo crear un recurso de otra persona para probarla. Así la regla
no depende de acordarse de escribir el test.
"""

import re
from collections.abc import Callable, Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from rinde.config import Settings
from rinde.main import create_app
from tests.fakes import (
    FakeDatabaseProbe,
    InMemoryAccountsUnitFactory,
    InMemoryAuthUnitFactory,
    InMemoryTransactionsUnitFactory,
)

CSRF = {"X-Requested-With": "rinde"}
PASSPHRASE = "mi gato come fideos los martes"
PARAMETER = re.compile(r"\{([^}]+)\}")

# Rutas que funcionan sin sesión, a propósito. Agregar una acá es una decisión de
# seguridad y tiene que poder justificarse.
PUBLIC_ROUTES = {
    ("GET", "/api/health/live"),
    ("GET", "/api/health/ready"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/recover"),
    # Cerrar una sesión que no existe no revela nada y deja limpia la cookie.
    ("POST", "/api/auth/logout"),
}


def _open_account(client: TestClient) -> str:
    response = client.post(
        "/api/accounts",
        json={"name": f"Cuenta {uuid4().hex[:8]}", "kind": "bank", "currency": "ARS"},
        headers=CSRF,
    )
    assert response.status_code == status.HTTP_201_CREATED
    identifier: str = response.json()["id"]
    return identifier


def _create_category(client: TestClient) -> str:
    # Nombre único: dos categorías del mismo tipo no pueden llamarse igual.
    response = client.post(
        "/api/categories",
        json={"name": f"Categoría {uuid4().hex[:8]}", "kind": "expense"},
        headers=CSRF,
    )
    assert response.status_code == status.HTTP_201_CREATED
    identifier: str = response.json()["id"]
    return identifier


def _register_transaction(client: TestClient) -> str:
    response = client.post(
        "/api/transactions",
        json={
            "account_id": _open_account(client),
            "kind": "expense",
            "amount": "1500.00",
            "category_id": _create_category(client),
            "occurred_on": "2026-09-11",
        },
        headers=CSRF,
    )
    assert response.status_code == status.HTTP_201_CREATED
    identifier: str = response.json()["id"]
    return identifier


def _register_transfer(client: TestClient) -> str:
    response = client.post(
        "/api/transfers",
        json={
            "from_account_id": _open_account(client),
            "to_account_id": _open_account(client),
            "sent": "1000.00",
            "received": "1000.00",
            "occurred_on": "2026-09-11",
        },
        headers=CSRF,
    )
    assert response.status_code == status.HTTP_201_CREATED
    identifier: str = response.json()["id"]
    return identifier


# Cómo crear, con la sesión activa, un recurso para cada parámetro de camino.
OWNED_RESOURCES: dict[str, Callable[[TestClient], str]] = {
    "account_id": _open_account,
    "category_id": _create_category,
    "transaction_id": _register_transaction,
    "transfer_id": _register_transfer,
}

# Un cuerpo válido para cada ruta con identificador que lo pide. Con un cuerpo
# inválido la respuesta sería 422 antes de mirar el dueño, y el test no probaría nada.
VALID_BODIES: dict[tuple[str, str], dict[str, Any]] = {
    ("PATCH", "/api/accounts/{account_id}"): {"name": "Nombre de la intrusa"},
    ("PATCH", "/api/categories/{category_id}"): {"name": "Categoría de la intrusa"},
    ("PATCH", "/api/transactions/{transaction_id}"): {
        "kind": "expense",
        "amount": "9999.00",
        "category_id": str(uuid4()),
        "occurred_on": "2026-09-11",
    },
    ("PATCH", "/api/transfers/{transfer_id}"): {
        "from_account_id": str(uuid4()),
        "to_account_id": str(uuid4()),
        "sent": "9999.00",
        "received": "9999.00",
        "occurred_on": "2026-09-11",
    },
}


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    accounts_factory = InMemoryAccountsUnitFactory()
    return create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=InMemoryAuthUnitFactory(),
        accounts_factory=accounts_factory,
        transactions_factory=InMemoryTransactionsUnitFactory(accounts_factory.accounts),
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def _routes(app: FastAPI) -> list[tuple[str, str, bool]]:
    """(método, ruta, pide cuerpo) de cada operación publicada."""
    return sorted(
        (method.upper(), path, "requestBody" in operation)
        for path, operations in app.openapi()["paths"].items()
        for method, operation in operations.items()
    )


def _sign_in_as(client: TestClient, username: str) -> None:
    client.cookies.clear()
    response = client.post(
        "/api/auth/register", json={"username": username, "password": PASSPHRASE}, headers=CSRF
    )
    if response.status_code == status.HTTP_409_CONFLICT:
        response = client.post(
            "/api/auth/login", json={"username": username, "password": PASSPHRASE}, headers=CSRF
        )
    assert response.status_code in {status.HTTP_201_CREATED, status.HTTP_204_NO_CONTENT}


def test_the_public_list_only_names_routes_that_exist(app: FastAPI) -> None:
    """Una ruta pública borrada o renombrada no puede quedar habilitada en la lista."""
    published = {(method, path) for method, path, _ in _routes(app)}

    assert published >= PUBLIC_ROUTES


def test_every_path_parameter_knows_how_to_create_a_foreign_resource(app: FastAPI) -> None:
    parameters = {name for _, path, _ in _routes(app) for name in PARAMETER.findall(path)}

    missing = parameters - OWNED_RESOURCES.keys()

    assert not missing, (
        "Estos parámetros de camino no tienen registrada la forma de crear un recurso "
        f"ajeno en OWNED_RESOURCES: {sorted(missing)}"
    )


def test_every_route_with_an_identifier_and_a_body_has_a_valid_example(app: FastAPI) -> None:
    missing = [
        f"{method} {path}"
        for method, path, has_body in _routes(app)
        if has_body and PARAMETER.search(path) and (method, path) not in VALID_BODIES
    ]

    assert not missing, f"Faltan cuerpos válidos en VALID_BODIES para: {missing}"


def test_without_a_session_every_private_route_answers_401(
    app: FastAPI, client: TestClient
) -> None:
    unprotected = []
    for method, path, _ in _routes(app):
        if (method, path) in PUBLIC_ROUTES:
            continue
        url = PARAMETER.sub(lambda _: str(uuid4()), path)
        body = VALID_BODIES.get((method, path), {})
        response = client.request(method, url, json=body, headers=CSRF)
        if response.status_code != status.HTTP_401_UNAUTHORIZED:
            unprotected.append(f"{method} {path} respondió {response.status_code}")

    assert not unprotected, f"Rutas privadas accesibles sin sesión: {unprotected}"


def test_someone_elses_resource_answers_as_if_it_did_not_exist(
    app: FastAPI, client: TestClient
) -> None:
    _sign_in_as(client, "duena")
    resources = {name: create(client) for name, create in OWNED_RESOURCES.items()}
    before = client.get(f"/api/accounts/{resources['account_id']}").json()

    _sign_in_as(client, "intrusa")
    leaks = []
    for method, path, _ in _routes(app):
        if not PARAMETER.search(path):
            continue
        url = PARAMETER.sub(lambda match: resources[match.group(1)], path)
        body = VALID_BODIES.get((method, path), {})
        response = client.request(method, url, json=body, headers=CSRF)
        if response.status_code != status.HTTP_404_NOT_FOUND:
            leaks.append(f"{method} {path} respondió {response.status_code}")

    assert not leaks, f"Rutas que no responden 404 ante un recurso ajeno: {leaks}"

    # Y nada cambió: ni el nombre ni el archivado de la dueña.
    _sign_in_as(client, "duena")
    assert client.get(f"/api/accounts/{resources['account_id']}").json() == before
