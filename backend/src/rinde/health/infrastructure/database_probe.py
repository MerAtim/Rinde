"""Adaptador: verifica la base de datos con la consulta más barata posible."""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


class SqlAlchemyDatabaseProbe:
    def __init__(self, engine: AsyncEngine, *, timeout_seconds: float = 2.0) -> None:
        self._engine = engine
        self._timeout_seconds = timeout_seconds

    async def is_reachable(self) -> bool:
        try:
            async with asyncio.timeout(self._timeout_seconds), self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError, OSError, TimeoutError:
            logger.warning("La base de datos no responde", exc_info=True)
            return False
        return True
