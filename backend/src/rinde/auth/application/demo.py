"""Caso de uso de la cuenta demo: una por visita, que vence sola (ADR-0028).

La demo es una cuenta más: el aislamiento entre personas es el de siempre. Lo
propio es cómo nace (sin contraseña que alguien conozca, con datos sembrados)
y cómo muere (vencida, se borra con todo lo suyo la próxima vez que alguien
crea una).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from rinde.auth.application.dependencies import AuthDependencies
from rinde.auth.application.ports import ClientAction, SecurityDetail, SecurityEvent
from rinde.auth.application.rate_limits import ensure_client_under_limit, record_client_action
from rinde.auth.application.sessions import SessionIssuer
from rinde.auth.domain.errors import DemoUnavailableError
from rinde.auth.domain.user import User
from rinde.auth.domain.username import DEMO_PREFIX, Username

DEMO_TTL = timedelta(hours=2)
# Una demo ocupa unos 35 kB de datos: 100, con índices, menos de 15 MB de los 500 (ADR-0028).
MAX_DEMOS = 100


@dataclass(frozen=True, slots=True)
class StartedDemo:
    username: str
    expires_at: datetime
    session_token: str


class StartDemo:
    """Crea la cuenta, la siembra y recién entonces abre su sesión."""

    def __init__(self, deps: AuthDependencies, issuer: SessionIssuer) -> None:
        self._deps = deps
        self._issuer = issuer

    async def execute(self, client: str | None = None) -> StartedDemo:
        deps = self._deps
        user, expires_at = await self._create(client)
        # Cada módulo siembra en su propia transacción: si algo falla a mitad de
        # camino, no se emite la sesión, nadie entra y la demo se borra al vencer.
        await deps.services.demo_seeder.seed(user.id)
        token = await self._issuer.issue(user.id, expires_at=expires_at)
        await deps.transaction.commit()
        deps.services.security_log.record(
            SecurityEvent.USER_CREATED, user.id, SecurityDetail.DEMO, client=client
        )
        return StartedDemo(
            username=user.username.value,
            expires_at=expires_at,
            session_token=token,
        )

    async def _create(self, client: str | None) -> tuple[User, datetime]:
        deps = self._deps
        services = deps.services
        now = services.clock.now()
        expires_at = now + DEMO_TTL

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
            demo_expires_at=expires_at,
        )
        await deps.users.add(user)
        await record_client_action(deps, ClientAction.DEMO, client)
        # Se confirma antes de sembrar: los otros módulos necesitan ver la cuenta.
        await deps.transaction.commit()
        return user, expires_at
