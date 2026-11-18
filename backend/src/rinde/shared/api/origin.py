"""Solo el Worker de Cloudflare habla con la API (ADR-0032).

El origen de la API tiene dirección pública. Sin este control, quien la llama
directo puede escribir a mano la cabecera con la dirección del visitante y
esquivar los límites por dirección. El Worker agrega un secreto a cada pedido,
y acá se rechaza todo lo que no lo traiga.

Va como middleware ASGI y no como dependencia: corta antes que cualquier otra
cosa, incluido leer el cuerpo, y vale para toda ruta, también las que no
existen.
"""

import hmac

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

HEADER = b"x-rinde-origin"
CODE = "ORIGIN_REJECTED"

OPEN_PATHS = frozenset({"/api/health/live", "/api/health/ready"})
"""Los usan el chequeo de salud de Render y el CD, que llegan directo.

No devuelven datos de nadie: solo si la API y la base responden.
"""


class OriginSecretMiddleware:
    def __init__(self, app: ASGIApp, *, secrets: tuple[str, ...]) -> None:
        if not secrets:
            msg = "El control de origen necesita al menos un secreto"
            raise ValueError(msg)
        self._app = app
        self._secrets = tuple(secret.encode() for secret in secrets)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in OPEN_PATHS:
            await self._app(scope, receive, send)
            return
        if self._accepts(dict(scope["headers"]).get(HEADER, b"")):
            await self._app(scope, receive, send)
            return
        await JSONResponse({"code": CODE}, status_code=403)(scope, receive, send)

    def _accepts(self, presented: bytes) -> bool:
        # Se comparan todos, sin cortar en el primero que coincide: el tiempo de
        # respuesta no dice cuál de los secretos se usó ni cuántos hay.
        accepted = False
        for secret in self._secrets:
            accepted |= hmac.compare_digest(presented, secret)
        return accepted
