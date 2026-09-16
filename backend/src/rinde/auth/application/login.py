"""Caso de uso: iniciar sesión sin revelar si la cuenta existe."""

from rinde.auth.application.dependencies import AuthDependencies
from rinde.auth.application.ports import ClientAction
from rinde.auth.application.rate_limits import ensure_client_under_limit, record_client_action
from rinde.auth.application.sessions import SessionIssuer, ensure_not_locked, record_failure
from rinde.auth.domain.errors import (
    InvalidCredentialsError,
    UsernameInvalidError,
    UsernameReservedError,
)
from rinde.auth.domain.password_policy import normalize_password
from rinde.auth.domain.username import Username


class LoginUser:
    def __init__(self, deps: AuthDependencies, issuer: SessionIssuer) -> None:
        self._deps = deps
        self._issuer = issuer

    async def execute(self, raw_username: str, password: str, client: str | None = None) -> str:
        """Devuelve el token de la sesión nueva."""
        deps = self._deps
        hasher = deps.services.hasher

        try:
            username = Username.parse(raw_username)
        except UsernameInvalidError, UsernameReservedError:
            raise InvalidCredentialsError from None
        await ensure_not_locked(deps, username)
        await ensure_client_under_limit(deps, ClientAction.LOGIN_FAILURE, client)

        normalized = normalize_password(password)
        user = await deps.users.by_username(username)
        # Con o sin cuenta se verifica un hash: el tiempo de respuesta no delata si existe.
        valid = await hasher.verify(user.password_hash if user else hasher.dummy_hash, normalized)
        if user is None or not valid:
            await record_client_action(deps, ClientAction.LOGIN_FAILURE, client)
            await record_failure(deps, username)
            raise InvalidCredentialsError

        if hasher.needs_rehash(user.password_hash):
            await deps.users.update_password_hash(user.id, await hasher.hash(normalized))
        await deps.failed_attempts.clear(username)
        token = await self._issuer.issue(user.id)
        await deps.transaction.commit()
        return token
