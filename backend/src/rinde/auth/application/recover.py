"""Caso de uso: recuperar la cuenta con el código, elegir otra contraseña y rotar el código."""

from dataclasses import dataclass

from rinde.auth.application.dependencies import AuthDependencies
from rinde.auth.application.ports import ClientAction
from rinde.auth.application.rate_limits import ensure_client_under_limit, record_client_action
from rinde.auth.application.sessions import SessionIssuer, ensure_not_locked, record_failure
from rinde.auth.domain.errors import (
    InvalidRecoveryCodeError,
    PasswordCompromisedError,
    UsernameInvalidError,
    UsernameReservedError,
)
from rinde.auth.domain.password_policy import check_password_policy
from rinde.auth.domain.recovery_code import format_recovery_code, normalize_recovery_code
from rinde.auth.domain.username import Username


@dataclass(frozen=True, slots=True)
class Recovery:
    recovery_code: str
    """Código nuevo: el anterior deja de servir."""
    session_token: str


class RecoverAccount:
    def __init__(self, deps: AuthDependencies, issuer: SessionIssuer) -> None:
        self._deps = deps
        self._issuer = issuer

    async def execute(
        self, raw_username: str, raw_code: str, new_password: str, client: str | None = None
    ) -> Recovery:
        deps = self._deps
        services = deps.services
        hasher = services.hasher

        try:
            username = Username.parse(raw_username)
        except UsernameInvalidError, UsernameReservedError:
            raise InvalidRecoveryCodeError from None
        await ensure_not_locked(deps, username)
        await ensure_client_under_limit(deps, ClientAction.LOGIN_FAILURE, client)
        normalized = check_password_policy(new_password, username)
        code = normalize_recovery_code(raw_code)

        user = await deps.users.by_username(username)
        secret_hash = user.recovery_code_hash if user else hasher.dummy_hash
        valid = await hasher.verify(secret_hash, code)
        if user is None or not valid:
            await record_client_action(deps, ClientAction.LOGIN_FAILURE, client)
            await record_failure(deps, username)
            raise InvalidRecoveryCodeError
        if await services.breaches.is_compromised(normalized):
            raise PasswordCompromisedError

        new_symbols = services.secrets.recovery_code()
        await deps.users.update_credentials(
            user.id,
            password_hash=await hasher.hash(normalized),
            recovery_code_hash=await hasher.hash(new_symbols),
        )
        # La cuenta pudo estar comprometida: se cierran todas las sesiones abiertas.
        await deps.sessions.delete_all_for_user(user.id)
        await deps.failed_attempts.clear(username)
        token = await self._issuer.issue(user.id)
        await deps.transaction.commit()
        return Recovery(recovery_code=format_recovery_code(new_symbols), session_token=token)
