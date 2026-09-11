"""Puertos del módulo de autenticación: lo que la aplicación necesita, sin decir cómo se hace."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from rinde.auth.domain.user import User
from rinde.auth.domain.username import Username


@dataclass(frozen=True, slots=True)
class Session:
    """Sesión abierta. Se guarda el hash del token, nunca el token."""

    token_hash: str
    user_id: UUID
    created_at: datetime
    expires_at: datetime


class UserRepository(Protocol):
    async def add(self, user: User) -> None: ...

    async def by_username(self, username: Username) -> User | None: ...

    async def by_id(self, user_id: UUID) -> User | None: ...

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None: ...

    async def update_credentials(
        self, user_id: UUID, *, password_hash: str, recovery_code_hash: str
    ) -> None: ...


class SessionRepository(Protocol):
    async def add(self, session: Session) -> None: ...

    async def by_token_hash(self, token_hash: str) -> Session | None: ...

    async def delete(self, token_hash: str) -> None: ...

    async def delete_all_for_user(self, user_id: UUID) -> None: ...


class FailedAttemptRepository(Protocol):
    async def count_since(self, username: Username, since: datetime) -> int: ...

    async def record(self, username: Username, at: datetime) -> None: ...

    async def clear(self, username: Username) -> None: ...


class PasswordHasher(Protocol):
    """Hash lento para secretos elegidos por personas.

    `dummy_hash` permite gastar el mismo tiempo cuando la cuenta no existe, para no revelarlo.
    """

    @property
    def dummy_hash(self) -> str: ...

    async def hash(self, secret: str) -> str: ...

    async def verify(self, secret_hash: str, secret: str) -> bool: ...

    def needs_rehash(self, secret_hash: str) -> bool: ...


class BreachedPasswordChecker(Protocol):
    async def is_compromised(self, password: str) -> bool: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class SecretGenerator(Protocol):
    def recovery_code(self) -> str: ...

    def session_token(self) -> str: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...
