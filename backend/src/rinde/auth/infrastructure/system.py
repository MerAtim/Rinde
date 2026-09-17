"""Generador de secretos del sistema operativo."""

import secrets

from rinde.auth.domain.recovery_code import ALPHABET, LENGTH


class SecureRandomSecrets:
    """Usa el generador criptográfico del sistema (módulo `secrets`), nunca `random`."""

    def recovery_code(self) -> str:
        return "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))

    def session_token(self) -> str:
        return secrets.token_urlsafe(32)
