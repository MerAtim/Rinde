"""Generador de secretos del sistema operativo."""

import secrets

from rinde.auth.domain.recovery_code import ALPHABET, LENGTH

_DEMO_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


class SecureRandomSecrets:
    """Usa el generador criptográfico del sistema (módulo `secrets`), nunca `random`."""

    def recovery_code(self) -> str:
        return "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))

    def session_token(self) -> str:
        return secrets.token_urlsafe(32)

    def demo_suffix(self) -> str:
        # 10 símbolos de 36: unos 51 bits, de sobra para no repetir entre 100 demos.
        return "".join(secrets.choice(_DEMO_ALPHABET) for _ in range(10))
