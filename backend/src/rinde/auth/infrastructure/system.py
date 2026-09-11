"""Reloj y generador de secretos del sistema operativo."""

import secrets
from datetime import UTC, datetime

from rinde.auth.domain.recovery_code import ALPHABET, LENGTH


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class SecureRandomSecrets:
    """Usa el generador criptográfico del sistema (módulo `secrets`), nunca `random`."""

    def recovery_code(self) -> str:
        return "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))

    def session_token(self) -> str:
        return secrets.token_urlsafe(32)
