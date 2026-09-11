"""Política de contraseñas según NIST SP 800-63B-4, con la contraseña como único factor."""

import unicodedata

from rinde.auth.domain.errors import (
    PasswordContainsUsernameError,
    PasswordTooLongError,
    PasswordTooShortError,
    PasswordTooSimpleError,
)
from rinde.auth.domain.username import Username

MIN_LENGTH = 15
MAX_LENGTH = 128
_MIN_DISTINCT_CHARACTERS = 3


def normalize_password(raw: str) -> str:
    """Normaliza Unicode (NFKC), como recomienda NIST.

    Así la misma frase vale igual escrita desde cualquier teclado.
    """
    return unicodedata.normalize("NFKC", raw)


def check_password_policy(password: str, username: Username) -> str:
    """Valida y devuelve la contraseña normalizada.

    Sin reglas de composición (NIST las prohíbe): solo largo, y nada trivial ni derivado del
    nombre de usuario. La comparación contra contraseñas filtradas ocurre en la aplicación.
    """
    normalized = normalize_password(password)
    if len(normalized) < MIN_LENGTH:
        raise PasswordTooShortError
    if len(normalized) > MAX_LENGTH:
        raise PasswordTooLongError
    if username.value in normalized.casefold():
        raise PasswordContainsUsernameError
    if len(set(normalized)) < _MIN_DISTINCT_CHARACTERS:
        raise PasswordTooSimpleError
    return normalized
