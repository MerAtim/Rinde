"""Caso de uso: borrar la cuenta propia con todos sus datos (ADR-0034).

La Ley 25.326 (art. 16) da derecho a pedir la supresión de los datos propios.
Se borra en el momento, sin período de gracia: la persona lo confirma con su
contraseña, como pide OWASP ASVS para una operación sensible, y así una sesión
olvidada abierta no alcanza para borrar la cuenta de otro.
"""

from uuid import UUID

from rinde.auth.application.dependencies import AuthDependencies
from rinde.auth.application.ports import ClientAction
from rinde.auth.application.rate_limits import ensure_client_under_limit, record_client_action
from rinde.auth.application.sessions import ensure_not_locked, record_failure
from rinde.auth.domain.errors import (
    DemoNotDeletableError,
    InvalidCredentialsError,
    NotAuthenticatedError,
)
from rinde.auth.domain.password_policy import normalize_password


class DeleteAccount:
    def __init__(self, deps: AuthDependencies) -> None:
        self._deps = deps

    async def execute(self, user_id: UUID, password: str, client: str | None = None) -> None:
        deps = self._deps
        hasher = deps.services.hasher

        user = await deps.users.by_id(user_id)
        if user is None:
            raise NotAuthenticatedError
        if user.is_demo:
            raise DemoNotDeletableError

        # La confirmación es una contraseña más para adivinar: cuenta para los
        # mismos topes que el inicio de sesión, por cuenta y por origen.
        await ensure_not_locked(deps, user.username)
        await ensure_client_under_limit(deps, ClientAction.LOGIN_FAILURE, client)
        if not await hasher.verify(user.password_hash, normalize_password(password)):
            await record_client_action(deps, ClientAction.LOGIN_FAILURE, client)
            await record_failure(deps, user.username)
            raise InvalidCredentialsError

        # La base borra las sesiones en cascada; se borran también acá para que
        # el caso de uso no dependa de cómo guarde los datos cada repositorio.
        await deps.sessions.delete_all_for_user(user.id)
        await deps.users.delete(user.id, at=deps.services.clock.now())
        # Los intentos fallidos guardan el nombre: también es un dato de la persona.
        await deps.failed_attempts.clear(user.username)
        await deps.transaction.commit()
