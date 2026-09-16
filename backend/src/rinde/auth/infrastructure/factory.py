"""Crea la unidad de trabajo de autenticación sobre PostgreSQL, una por pedido."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rinde.auth.application.dependencies import AuthDependencies, AuthServices
from rinde.auth.application.unit import AuthUnit, build_auth_unit
from rinde.auth.infrastructure.repositories import (
    SqlAlchemyClientActivityRepository,
    SqlAlchemyFailedAttemptRepository,
    SqlAlchemySessionRepository,
    SqlAlchemyTransaction,
    SqlAlchemyUserRepository,
)


class SqlAlchemyAuthUnitFactory:
    def __init__(
        self, sessionmaker: async_sessionmaker[AsyncSession], services: AuthServices
    ) -> None:
        self._sessionmaker = sessionmaker
        self._services = services

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AuthUnit]:
        # Si el pedido falla antes de confirmar, al cerrar la sesión se descarta la transacción.
        async with self._sessionmaker() as session:
            yield build_auth_unit(
                AuthDependencies(
                    users=SqlAlchemyUserRepository(session),
                    sessions=SqlAlchemySessionRepository(session),
                    failed_attempts=SqlAlchemyFailedAttemptRepository(session),
                    client_activity=SqlAlchemyClientActivityRepository(session),
                    transaction=SqlAlchemyTransaction(session),
                    services=self._services,
                )
            )
