"""Límite de tamaño del cuerpo de cada pedido, antes de que nadie lo lea.

FastAPI lee el cuerpo, incluido un archivo, antes de correr las dependencias
de un endpoint: un control de tamaño ahí llega tarde. Este middleware ASGI
corta el pedido apenas se pasa del límite: primero por `Content-Length`, y
después contando los bytes que llegan, porque esa cabecera puede faltar o
mentir (OWASP, "File Upload Cheat Sheet").
"""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CODE = "REQUEST_TOO_LARGE"


class BodyTooLargeError(Exception):
    pass


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self._max_bytes):
            await _too_large(send)
            return

        received = 0
        started = False

        async def counted_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    raise BodyTooLargeError
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self._app(scope, counted_receive, tracked_send)
        except BodyTooLargeError:
            # Si la respuesta ya empezó no se puede cambiar: el cliente ve la conexión cortada.
            if not started:
                await _too_large(send)


async def _too_large(send: Send) -> None:
    body = json.dumps({"code": CODE}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
