"""Caso de uso: los datos de la cuenta para la exportación (ADR-0034).

Devuelve solo lo que la persona cargó o le corresponde ver. Los hashes de la
contraseña y del código de recuperación no salen de este módulo: no son datos
de la persona sino la forma de verificarla, y exportarlos ayudaría a quien
robe el archivo a atacarlos sin conexión.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from rinde.auth.application.dependencies import AuthDependencies
from rinde.auth.domain.errors import NotAuthenticatedError


@dataclass(frozen=True, slots=True)
class Profile:
    id: UUID
    username: str
    created_at: datetime
    demo_expires_at: datetime | None


class GetProfile:
    def __init__(self, deps: AuthDependencies) -> None:
        self._deps = deps

    async def execute(self, user_id: UUID) -> Profile:
        user = await self._deps.users.by_id(user_id)
        if user is None:
            raise NotAuthenticatedError
        return Profile(
            id=user.id,
            username=user.username.value,
            created_at=user.created_at,
            demo_expires_at=user.demo_expires_at,
        )
