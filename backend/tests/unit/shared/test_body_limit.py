"""El límite de tamaño del cuerpo, antes de que nadie lo lea."""

from collections.abc import Iterator

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from rinde.shared.api.body_limit import BodySizeLimitMiddleware

LIMIT = 100


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=LIMIT)

    @app.post("/eco")
    async def echo(request: Request) -> dict[str, int]:
        return {"bytes": len(await request.body())}

    @app.get("/hola")
    async def hello() -> dict[str, str]:
        return {"hola": "mundo"}

    return app


def test_a_body_within_the_limit_passes() -> None:
    with TestClient(_app()) as client:
        response = client.post("/eco", content=b"x" * LIMIT)

    assert response.json() == {"bytes": LIMIT}


def test_a_declared_length_over_the_limit_is_rejected_at_once() -> None:
    with TestClient(_app()) as client:
        response = client.post("/eco", content=b"x" * (LIMIT + 1))

    assert response.status_code == 413
    assert response.json() == {"code": "REQUEST_TOO_LARGE"}


def test_a_body_without_length_is_counted_as_it_arrives() -> None:
    """Con transferencia por partes no hay Content-Length: se cuentan los bytes."""

    def chunks() -> Iterator[bytes]:
        for _ in range(5):
            yield b"x" * 40

    with TestClient(_app()) as client:
        response = client.post("/eco", content=chunks())

    assert response.status_code == 413
    assert response.json() == {"code": "REQUEST_TOO_LARGE"}


def test_a_lying_length_is_rejected() -> None:
    with TestClient(_app()) as client:
        response = client.post("/eco", content=b"x", headers={"Content-Length": "abc"})

    assert response.status_code == 413


def test_requests_without_body_are_untouched() -> None:
    with TestClient(_app()) as client:
        assert client.get("/hola").json() == {"hola": "mundo"}
