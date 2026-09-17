"""Quién hace el pedido, para los módulos que necesitan saberlo.

Un módulo no puede depender de la capa api de otro, así que `accounts` no puede
leer la cookie de sesión de `auth`. La raíz de composición registra en
`app.state.identify` cómo resolver la identidad, y cada módulo solo pide el
identificador con `CurrentUserId`.

Si no hay sesión válida, el resolvedor lanza el error de `auth`, que la API
traduce a 401. Por eso un endpoint que pide `CurrentUserId` ya está protegido.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

Identify = Callable[[Request], Awaitable[UUID]]


async def current_user_id(request: Request) -> UUID:
    identify: Identify = request.app.state.identify
    return await identify(request)


CurrentUserId = Annotated[UUID, Depends(current_user_id)]
