"""Caso de uso: crear una cuenta con usuario, contraseña y código de recuperación."""

from dataclasses import dataclass
from uuid import uuid4

from rinde.auth.application.dependencies import AuthDependencies
from rinde.auth.application.ports import ClientAction
from rinde.auth.application.rate_limits import ensure_client_under_limit, record_client_action
from rinde.auth.application.sessions import SessionIssuer
from rinde.auth.domain.errors import PasswordCompromisedError, UsernameTakenError
from rinde.auth.domain.password_policy import check_password_policy
from rinde.auth.domain.recovery_code import format_recovery_code
from rinde.auth.domain.user import User
from rinde.auth.domain.username import Username


@dataclass(frozen=True, slots=True)
class Registration:
    user: User
    recovery_code: str
    """Se muestra una sola vez: la base guarda solo su hash."""
    session_token: str


class RegisterUser:
    def __init__(self, deps: AuthDependencies, issuer: SessionIssuer) -> None:
        self._deps = deps
        self._issuer = issuer

    async def execute(
        self, raw_username: str, password: str, client: str | None = None
    ) -> Registration:
        deps = self._deps
        services = deps.services

        await ensure_client_under_limit(deps, ClientAction.REGISTRATION, client)
        username = Username.parse(raw_username)
        if await deps.users.by_username(username) is not None:
            raise UsernameTakenError
        normalized = check_password_policy(password, username)
        if await services.breaches.is_compromised(normalized):
            raise PasswordCompromisedError

        recovery_symbols = services.secrets.recovery_code()
        user = User(
            id=uuid4(),
            username=username,
            password_hash=await services.hasher.hash(normalized),
            recovery_code_hash=await services.hasher.hash(recovery_symbols),
            created_at=services.clock.now(),
        )
        await deps.users.add(user)
        await record_client_action(deps, ClientAction.REGISTRATION, client)
        token = await self._issuer.issue(user.id)
        await deps.transaction.commit()
        return Registration(
            user=user,
            recovery_code=format_recovery_code(recovery_symbols),
            session_token=token,
        )
