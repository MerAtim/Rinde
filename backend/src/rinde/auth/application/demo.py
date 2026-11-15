"""Casos de uso de la cuenta demo: una por visita, que vence sola (ADR-0028).

La demo es una cuenta más: el aislamiento entre personas es el de siempre. Lo
propio es cómo nace (sin contraseña que alguien conozca) y cómo muere (vencida,
se borra con todo lo suyo la próxima vez que alguien crea una).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from rinde.auth.application.dependencies import AuthDependencies
from rinde.auth.application.ports import ClientAction
from rinde.auth.application.rate_limits import ensure_client_under_limit, record_client_action
from rinde.auth.application.sessions import SessionIssuer
from rinde.auth.domain.errors import DemoUnavailableError, NotAuthenticatedError
from rinde.auth.domain.user import User
from rinde.auth.domain.username import DEMO_PREFIX, Username

DEMO_TTL = timedelta(hours=2)
# Con unos 200 kB por demo, 100 ocupan unos 20 MB de los 500 de la base (ADR-0028).
MAX_DEMOS = 100


@dataclass(frozen=True, slots=True)
class DemoUser:
    id: UUID
    username: str
    expires_at: datetime


class CreateDemoUser:
    """Crea la cuenta, todavía sin sesión: la sesión se emite cuando está sembrada."""

    def __init__(self, deps: AuthDependencies) -> None:
        self._deps = deps

    async def execute(self, client: str | None = None) -> DemoUser:
        deps = self._deps
        services = deps.services
        now = services.clock.now()

        # Con el lock, contar y crear es atómico: dos pedidos a la vez no pasan
        # juntos el tope. Se toma antes de borrar para no pisar otra limpieza.
        await deps.users.lock_demos()
        await deps.users.purge_expired_demos(now)
        await ensure_client_under_limit(deps, ClientAction.DEMO, client)
        if await deps.users.count_demos() >= MAX_DEMOS:
            # Cuando venza la próxima, como mucho: la más vieja tiene menos de DEMO_TTL.
            raise DemoUnavailableError(retry_after_seconds=int(DEMO_TTL.total_seconds()))

        # Secretos que no se guardan en ningún lado: nadie puede iniciar sesión ni
        # recuperar una demo. Se entra solo con la sesión que se emite al crearla.
        user = User(
            id=uuid4(),
            username=Username.parse(DEMO_PREFIX + services.secrets.demo_suffix()),
            password_hash=await services.hasher.hash(services.secrets.session_token()),
            recovery_code_hash=await services.hasher.hash(services.secrets.session_token()),
            created_at=now,
            demo_expires_at=now + DEMO_TTL,
        )
        await deps.users.add(user)
        await record_client_action(deps, ClientAction.DEMO, client)
        await deps.transaction.commit()
        return DemoUser(id=user.id, username=user.username.value, expires_at=now + DEMO_TTL)


class StartDemoSession:
    """Abre la sesión de una demo, que vence con ella."""

    def __init__(self, deps: AuthDependencies, issuer: SessionIssuer) -> None:
        self._deps = deps
        self._issuer = issuer

    async def execute(self, user_id: UUID) -> str:
        deps = self._deps
        user = await deps.users.by_id(user_id)
        # Solo una demo vigente: este caso de uso no abre sesiones de cuentas comunes.
        if (
            user is None
            or user.demo_expires_at is None
            or user.is_expired(deps.services.clock.now())
        ):
            raise NotAuthenticatedError
        token = await self._issuer.issue(user.id, expires_at=user.demo_expires_at)
        await deps.transaction.commit()
        return token
