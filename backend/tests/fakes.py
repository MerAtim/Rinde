"""Implementaciones en memoria de los puertos, para tests sin infraestructura."""

from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from rinde.auth.application.dependencies import AuthDependencies, AuthServices
from rinde.auth.application.ports import Session
from rinde.auth.application.unit import AuthUnit, build_auth_unit
from rinde.auth.domain.errors import UsernameTakenError
from rinde.auth.domain.user import User
from rinde.auth.domain.username import Username


class FakeDatabaseProbe:
    def __init__(self, *, reachable: bool) -> None:
        self.reachable = reachable
        self.calls = 0

    async def is_reachable(self) -> bool:
        self.calls += 1
        return self.reachable


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 9, 11, 12, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


class FakeHasher:
    """Hash legible para tests. `version` simula un cambio de parámetros del algoritmo."""

    dummy_hash = "hash:dummy"

    def __init__(self) -> None:
        self.version = 1
        self.verify_calls = 0

    async def hash(self, secret: str) -> str:
        return f"hash:v{self.version}:{secret}"

    async def verify(self, secret_hash: str, secret: str) -> bool:
        self.verify_calls += 1
        parts = secret_hash.split(":", 2)
        return len(parts) == 3 and parts[1].startswith("v") and parts[2] == secret

    def needs_rehash(self, secret_hash: str) -> bool:
        return not secret_hash.startswith(f"hash:v{self.version}:")


class FakeBreachChecker:
    def __init__(self, compromised: Iterable[str] = ()) -> None:
        self.compromised = set(compromised)

    async def is_compromised(self, password: str) -> bool:
        return password in self.compromised


class FakeSecrets:
    def __init__(self) -> None:
        self._counter = 0

    def recovery_code(self) -> str:
        self._counter += 1
        return f"{self._counter:020d}"

    def session_token(self) -> str:
        self._counter += 1
        return f"token-{self._counter}"


class InMemoryUsers:
    def __init__(self) -> None:
        self.store: dict[UUID, User] = {}

    async def add(self, user: User) -> None:
        if any(existing.username == user.username for existing in self.store.values()):
            raise UsernameTakenError
        self.store[user.id] = user

    async def by_username(self, username: Username) -> User | None:
        return next((user for user in self.store.values() if user.username == username), None)

    async def by_id(self, user_id: UUID) -> User | None:
        return self.store.get(user_id)

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        self.store[user_id] = replace(self.store[user_id], password_hash=password_hash)

    async def update_credentials(
        self, user_id: UUID, *, password_hash: str, recovery_code_hash: str
    ) -> None:
        self.store[user_id] = replace(
            self.store[user_id],
            password_hash=password_hash,
            recovery_code_hash=recovery_code_hash,
        )


class InMemorySessions:
    def __init__(self) -> None:
        self.store: dict[str, Session] = {}

    async def add(self, session: Session) -> None:
        self.store[session.token_hash] = session

    async def by_token_hash(self, token_hash: str) -> Session | None:
        return self.store.get(token_hash)

    async def delete(self, token_hash: str) -> None:
        self.store.pop(token_hash, None)

    async def delete_all_for_user(self, user_id: UUID) -> None:
        self.store = {key: s for key, s in self.store.items() if s.user_id != user_id}


class InMemoryFailedAttempts:
    def __init__(self) -> None:
        self.attempts: list[tuple[Username, datetime]] = []

    async def count_since(self, username: Username, since: datetime) -> int:
        return sum(1 for who, at in self.attempts if who == username and at >= since)

    async def record(self, username: Username, at: datetime) -> None:
        self.attempts.append((username, at))

    async def clear(self, username: Username) -> None:
        self.attempts = [(who, at) for who, at in self.attempts if who != username]


class FakeTransaction:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class InMemoryAuthUnitFactory:
    """Estado compartido entre pedidos, como si fuera la base de datos."""

    def __init__(self, *, compromised: Iterable[str] = ()) -> None:
        self.users = InMemoryUsers()
        self.sessions = InMemorySessions()
        self.failed_attempts = InMemoryFailedAttempts()
        self.transaction = FakeTransaction()
        self.hasher = FakeHasher()
        self.clock = FakeClock()
        self.services = AuthServices(
            hasher=self.hasher,
            breaches=FakeBreachChecker(compromised),
            clock=self.clock,
            secrets=FakeSecrets(),
            session_ttl=timedelta(days=30),
        )

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AuthUnit]:
        yield build_auth_unit(
            AuthDependencies(
                users=self.users,
                sessions=self.sessions,
                failed_attempts=self.failed_attempts,
                transaction=self.transaction,
                services=self.services,
            )
        )
