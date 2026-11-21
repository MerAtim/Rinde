"""Repositorios de autenticación sobre PostgreSQL. No confirman: lo hace la transacción."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import RowMapping, delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rinde.auth.application.ports import ClientAction, Session
from rinde.auth.domain.errors import UsernameTakenError
from rinde.auth.domain.user import User
from rinde.auth.domain.username import Username
from rinde.auth.infrastructure.tables import (
    account_deletions,
    client_activity,
    failed_login_attempts,
    sessions,
    users,
)

# Clave del lock que serializa la creación y el borrado de demos. Cualquier
# número fijo sirve mientras ningún otro lock use el mismo.
DEMO_LOCK = 0x52494E4445_00_01


def _to_user(row: RowMapping) -> User:
    return User(
        id=row["id"],
        username=Username(row["username"]),
        password_hash=row["password_hash"],
        recovery_code_hash=row["recovery_code_hash"],
        created_at=row["created_at"],
        demo_expires_at=row["demo_expires_at"],
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        try:
            await self._session.execute(
                insert(users).values(
                    id=user.id,
                    username=user.username.value,
                    password_hash=user.password_hash,
                    recovery_code_hash=user.recovery_code_hash,
                    created_at=user.created_at,
                    demo_expires_at=user.demo_expires_at,
                )
            )
        except IntegrityError as error:
            # Dos registros simultáneos con el mismo nombre: la restricción UNIQUE decide.
            raise UsernameTakenError from error

    async def by_username(self, username: Username) -> User | None:
        result = await self._session.execute(
            select(users).where(users.c.username == username.value)
        )
        row = result.mappings().one_or_none()
        return None if row is None else _to_user(row)

    async def by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(select(users).where(users.c.id == user_id))
        row = result.mappings().one_or_none()
        return None if row is None else _to_user(row)

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        await self._session.execute(
            update(users).where(users.c.id == user_id).values(password_hash=password_hash)
        )

    async def update_credentials(
        self, user_id: UUID, *, password_hash: str, recovery_code_hash: str
    ) -> None:
        await self._session.execute(
            update(users)
            .where(users.c.id == user_id)
            .values(password_hash=password_hash, recovery_code_hash=recovery_code_hash)
        )

    async def lock_demos(self) -> None:
        await self._session.execute(select(func.pg_advisory_xact_lock(DEMO_LOCK)))

    async def count_demos(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(users).where(users.c.demo_expires_at.is_not(None))
        )
        return int(result.scalar_one())

    async def purge_expired_demos(self, now: datetime) -> None:
        # Las claves foráneas con ON DELETE CASCADE se llevan todo lo de la demo,
        # auditoría incluida (ADR-0028).
        await self._session.execute(
            delete(users).where(
                users.c.demo_expires_at.is_not(None), users.c.demo_expires_at <= now
            )
        )

    async def delete(self, user_id: UUID, *, at: datetime) -> None:
        # ON DELETE CASCADE se lleva todo lo de la cuenta, auditoría incluida.
        # La constancia va en la misma transacción: no hay baja sin registro.
        await self._session.execute(
            insert(account_deletions).values(user_id=user_id, deleted_at=at)
        )
        await self._session.execute(delete(users).where(users.c.id == user_id))


class SqlAlchemySessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, session: Session) -> None:
        await self._session.execute(
            insert(sessions).values(
                token_hash=session.token_hash,
                user_id=session.user_id,
                created_at=session.created_at,
                expires_at=session.expires_at,
            )
        )

    async def by_token_hash(self, token_hash: str) -> Session | None:
        result = await self._session.execute(
            select(sessions).where(sessions.c.token_hash == token_hash)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return Session(
            token_hash=row["token_hash"],
            user_id=row["user_id"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
        )

    async def delete(self, token_hash: str) -> None:
        await self._session.execute(delete(sessions).where(sessions.c.token_hash == token_hash))

    async def delete_all_for_user(self, user_id: UUID) -> None:
        await self._session.execute(delete(sessions).where(sessions.c.user_id == user_id))


class SqlAlchemyFailedAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_since(self, username: Username, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(failed_login_attempts)
            .where(
                failed_login_attempts.c.username == username.value,
                failed_login_attempts.c.attempted_at >= since,
            )
        )
        return int(result.scalar_one())

    async def record(self, username: Username, at: datetime) -> None:
        await self._session.execute(
            insert(failed_login_attempts).values(username=username.value, attempted_at=at)
        )

    async def clear(self, username: Username) -> None:
        await self._session.execute(
            delete(failed_login_attempts).where(failed_login_attempts.c.username == username.value)
        )

    async def purge_before(self, cutoff: datetime) -> None:
        await self._session.execute(
            delete(failed_login_attempts).where(failed_login_attempts.c.attempted_at < cutoff)
        )


class SqlAlchemyClientActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_since(self, action: ClientAction, client: str, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(client_activity)
            .where(
                client_activity.c.action == action.value,
                client_activity.c.client == client,
                client_activity.c.occurred_at >= since,
            )
        )
        return int(result.scalar_one())

    async def record(self, action: ClientAction, client: str, at: datetime) -> None:
        await self._session.execute(
            insert(client_activity).values(action=action.value, client=client, occurred_at=at)
        )

    async def purge_before(self, cutoff: datetime) -> None:
        await self._session.execute(
            delete(client_activity).where(client_activity.c.occurred_at < cutoff)
        )


class SqlAlchemyTransaction:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()
