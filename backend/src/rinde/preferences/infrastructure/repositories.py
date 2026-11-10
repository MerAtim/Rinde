"""Repositorio de preferencias sobre PostgreSQL. No confirma: lo hace la transacción."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rinde.preferences.domain.preferences import Preferences
from rinde.preferences.infrastructure.tables import user_preferences
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType


class SqlAlchemyPreferencesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, owner_id: UUID) -> Preferences | None:
        result = await self._session.execute(
            select(user_preferences).where(user_preferences.c.owner_id == owner_id)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return Preferences(
            owner_id=row["owner_id"],
            reference_currency=Currency(row["reference_currency"]),
            rate_type=RateType(row["rate_type"]),
            updated_at=row["updated_at"],
        )

    async def save(self, preferences: Preferences) -> None:
        values = {
            "reference_currency": preferences.reference_currency.value,
            "rate_type": preferences.rate_type.value,
            "updated_at": preferences.updated_at,
        }
        # Un solo pedido, sin leer antes: dos cambios a la vez no chocan, gana el último.
        await self._session.execute(
            insert(user_preferences)
            .values(owner_id=preferences.owner_id, **values)
            .on_conflict_do_update(index_elements=[user_preferences.c.owner_id], set_=values)
        )
