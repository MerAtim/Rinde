"""De dónde sale la dirección de origen, con dos proxies en el medio.

Es un dato que viene de afuera y termina en la base, así que se valida como
cualquier entrada no confiable.
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rinde.auth.api.client import ClientAddress


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = FastAPI()

    @app.get("/quien")
    async def quien(address: ClientAddress) -> dict[str, str | None]:
        return {"address": address}

    with TestClient(app) as test_client:
        yield test_client


def _address(client: TestClient, headers: dict[str, str]) -> str | None:
    address: str | None = client.get("/quien", headers=headers).json()["address"]
    return address


def test_cloudflare_wins_over_the_forwarded_chain(client: TestClient) -> None:
    """Cloudflare reescribe su cabecera en el borde; la otra la pone cualquiera."""
    address = _address(
        client,
        {"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "198.51.100.4"},
    )

    assert address == "203.0.113.7"


def test_the_forwarded_chain_uses_the_first_address(client: TestClient) -> None:
    address = _address(client, {"X-Forwarded-For": "203.0.113.7, 198.51.100.4, 10.0.0.1"})

    assert address == "203.0.113.7"


def test_ipv6_is_accepted(client: TestClient) -> None:
    address = _address(client, {"CF-Connecting-IP": "2001:db8::1"})

    assert address == "2001:db8::1"


@pytest.mark.parametrize(
    "value",
    [
        "no-es-una-direccion",
        "999.999.999.999",
        "203.0.113.7; drop table users",
        "",
        "a" * 200,
    ],
)
def test_a_made_up_header_is_ignored(client: TestClient, value: str) -> None:
    """Sin dirección válida se devuelve None y el límite falla abierto.

    Meter lo que no se entiende en una misma bolsa dejaría a cualquiera bloquear
    a todos los demás con una cabecera inventada.
    """
    assert _address(client, {"CF-Connecting-IP": value}) is None
