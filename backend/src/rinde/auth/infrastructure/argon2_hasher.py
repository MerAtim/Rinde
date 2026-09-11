"""Hash de contraseñas y códigos con argon2id (ADR-0007)."""

import asyncio
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


class Argon2PasswordHasher:
    """argon2id con el mínimo recomendado por OWASP: 19 MiB, 2 iteraciones, 1 hilo.

    Render Free tiene 0,1 CPU y 512 MB: más hilos no aceleran y más memoria arriesga el
    servicio. El cálculo corre en un hilo aparte para no frenar al resto de los pedidos.
    """

    def __init__(self) -> None:
        self._argon2 = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
        self.dummy_hash = self._argon2.hash(secrets.token_urlsafe(16))

    async def hash(self, secret: str) -> str:
        return await asyncio.to_thread(self._argon2.hash, secret)

    async def verify(self, secret_hash: str, secret: str) -> bool:
        try:
            return await asyncio.to_thread(self._argon2.verify, secret_hash, secret)
        except VerificationError, InvalidHashError:
            return False

    def needs_rehash(self, secret_hash: str) -> bool:
        return self._argon2.check_needs_rehash(secret_hash)
