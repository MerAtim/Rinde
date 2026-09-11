from collections.abc import AsyncIterator

from fastapi import Request

from rinde.auth.application.unit import AuthUnit, AuthUnitFactory


async def auth_unit(request: Request) -> AsyncIterator[AuthUnit]:
    """Una unidad de trabajo por pedido: si algo falla, su transacción se descarta."""
    factory: AuthUnitFactory = request.app.state.auth_factory
    async with factory() as unit:
        yield unit
