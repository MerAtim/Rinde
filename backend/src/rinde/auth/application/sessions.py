"""Emisión de sesiones y control de intentos fallidos, compartidos por varios casos de uso."""

import hashlib
from datetime import datetime, timedelta
from uuid import UUID

from rinde.auth.application.dependencies import AuthDependencies
from rinde.auth.application.ports import SecurityDetail, SecurityEvent, Session
from rinde.auth.domain.errors import TooManyAttemptsError
from rinde.auth.domain.user import User
from rinde.auth.domain.username import Username

# NIST SP 800-63B-4 exige limitar los intentos fallidos sobre cada cuenta.
MAX_FAILED_ATTEMPTS = 10
ATTEMPT_WINDOW = timedelta(minutes=15)


def hash_token(token: str) -> str:
    """El token tiene 256 bits de azar: SHA-256 alcanza, y la base nunca guarda el token."""
    return hashlib.sha256(token.encode()).hexdigest()


class SessionIssuer:
    def __init__(self, deps: AuthDependencies) -> None:
        self._deps = deps

    async def issue(self, user_id: UUID, *, expires_at: datetime | None = None) -> str:
        """Sin `expires_at`, la sesión dura lo de siempre; una demo la acorta a su vencimiento."""
        services = self._deps.services
        token = services.secrets.session_token()
        now = services.clock.now()
        await self._deps.sessions.add(
            Session(
                token_hash=hash_token(token),
                user_id=user_id,
                created_at=now,
                expires_at=expires_at or now + services.session_ttl,
            )
        )
        return token


def known_account(user: User | None) -> tuple[UUID, ...]:
    """El identificador para el registro de seguridad, si la cuenta existe."""
    return (user.id,) if user else ()


async def ensure_not_locked(
    deps: AuthDependencies, username: Username, user: User | None, client: str | None
) -> None:
    since = deps.services.clock.now() - ATTEMPT_WINDOW
    if await deps.failed_attempts.count_since(username, since) >= MAX_FAILED_ATTEMPTS:
        deps.services.security_log.record(
            SecurityEvent.ACCOUNT_LOCKED,
            *known_account(user),
            SecurityDetail.MAX_RETRIES,
            client=client,
        )
        raise TooManyAttemptsError(retry_after_seconds=int(ATTEMPT_WINDOW.total_seconds()))


async def record_failure(deps: AuthDependencies, username: Username) -> None:
    """Registra el intento fallido y lo confirma antes de responder con el error.

    Aprovecha el paso para borrar los intentos que ya salieron de la ventana:
    el plan gratuito de Render no tiene programador de tareas, así que la
    limpieza va donde hay escritura.
    """
    now = deps.services.clock.now()
    await deps.failed_attempts.record(username, now)
    await deps.failed_attempts.purge_before(now - ATTEMPT_WINDOW)
    await deps.transaction.commit()
