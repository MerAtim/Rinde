"""Crea la unidad de trabajo de preferencias sobre PostgreSQL, una por pedido."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rinde.preferences.application.ports import Clock
from rinde.preferences.application.unit import PreferencesUnit, build_preferences_unit
from rinde.preferences.application.use_cases import PreferencesDependencies
from rinde.preferences.infrastructure.repositories import SqlAlchemyPreferencesRepository


class SqlAlchemyTransaction:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()


class SqlAlchemyPreferencesUnitFactory:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], clock: Clock) -> None:
        self._sessionmaker = sessionmaker
        self._clock = clock

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[PreferencesUnit]:
        async with self._sessionmaker() as session:
            yield build_preferences_unit(
                PreferencesDependencies(
                    preferences=SqlAlchemyPreferencesRepository(session),
                    transaction=SqlAlchemyTransaction(session),
                    clock=self._clock,
                )
            )
