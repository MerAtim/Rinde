"""Puertos del módulo de autenticación: lo que la aplicación necesita, sin decir cómo se hace."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
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

    async def lock_demos(self) -> None:
        """Hasta el final de la transacción, nadie más crea ni borra demos."""
        ...

    async def count_demos(self) -> int: ...

    async def purge_expired_demos(self, now: datetime) -> None:
        """Borra las demos vencidas y, en cascada, todos sus datos."""
        ...

    async def delete(self, user_id: UUID, *, at: datetime) -> None:
        """Borra la cuenta y, en cascada, todos sus datos, y deja constancia de la baja.

        La constancia guarda solo el identificador y la fecha: sirve para volver
        a borrar la cuenta si se restaura un respaldo anterior (ADR-0034).
        """
        ...


class SessionRepository(Protocol):
    async def add(self, session: Session) -> None: ...

    async def by_token_hash(self, token_hash: str) -> Session | None: ...

    async def delete(self, token_hash: str) -> None: ...

    async def delete_all_for_user(self, user_id: UUID) -> None: ...


class FailedAttemptRepository(Protocol):
    async def count_since(self, username: Username, since: datetime) -> int: ...

    async def record(self, username: Username, at: datetime) -> None: ...

    async def clear(self, username: Username) -> None: ...

    async def purge_before(self, cutoff: datetime) -> None:
        """Borra los intentos que ya no cuentan para ninguna ventana."""
        ...


class ClientAction(StrEnum):
    """Lo que se cuenta por dirección de origen."""

    LOGIN_FAILURE = "login_failure"
    REGISTRATION = "registration"
    DEMO = "demo"


class ClientActivityRepository(Protocol):
    """Cuenta acciones por dirección de origen, no por cuenta."""

    async def count_since(self, action: ClientAction, client: str, since: datetime) -> int: ...

    async def record(self, action: ClientAction, client: str, at: datetime) -> None: ...

    async def purge_before(self, cutoff: datetime) -> None: ...


class DemoSeeder(Protocol):
    """Llena una demo recién creada con datos de ejemplo (ADR-0028).

    Lo implementa otro módulo: auth no sabe qué es una cuenta ni un movimiento.
    """

    async def seed(self, owner_id: UUID) -> None: ...


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

    def demo_suffix(self) -> str:
        """Lo que sigue a `demo-` en el nombre de una demo."""
        ...


class Transaction(Protocol):
    async def commit(self) -> None: ...


class SecurityEvent(StrEnum):
    """Hechos de seguridad que se registran (ADR-0035).

    Los nombres son los del OWASP Logging Vocabulary; `authn_reauth_fail` es
    propio, con la misma forma, porque el vocabulario no distingue la contraseña
    que confirma una operación sensible de la que abre una sesión.
    """

    LOGIN_SUCCEEDED = "authn_login_success"
    LOGIN_FAILED = "authn_login_fail"
    ACCOUNT_LOCKED = "authn_login_lock"
    REAUTHENTICATION_FAILED = "authn_reauth_fail"
    PASSWORD_CHANGED = "authn_password_change"  # noqa: S105  (nombre de un evento, no una contraseña)
    PASSWORD_CHANGE_FAILED = "authn_password_change_fail"  # noqa: S105  (nombre de un evento)
    RATE_LIMIT_EXCEEDED = "excess_rate_limit_exceeded"
    SESSION_ENDED = "session_expired"
    SESSION_USED_AFTER_EXPIRY = "session_use_after_expire"
    USER_CREATED = "user_created"
    USER_DELETED = "user_deleted"


class SecurityDetail(StrEnum):
    """Los motivos y atributos que acompañan a un evento, con los valores del vocabulario."""

    MAX_RETRIES = "maxretries"
    LOGOUT = "logout"
    DEMO = "demo"


type SecurityParam = UUID | ClientAction | SecurityDetail | int
"""Solo identificadores internos, valores cerrados y números.

El tipo es la garantía: mypy rechaza pasar un `str` o un `Username`, así que ni
el nombre de usuario ni un secreto pueden terminar en el registro por descuido.
"""


class SecurityLog(Protocol):
    def record(
        self, event: SecurityEvent, *params: SecurityParam, client: str | None = None
    ) -> None:
        """Registra el hecho; no falla ni frena el pedido si el destino no responde."""
        ...
