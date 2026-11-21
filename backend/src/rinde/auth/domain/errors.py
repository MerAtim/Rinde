"""Errores de autenticación. Cada uno lleva un código estable que la API devuelve tal cual."""

from typing import ClassVar


class AuthError(Exception):
    code: ClassVar[str] = "AUTH_ERROR"


class UsernameInvalidError(AuthError):
    code = "USERNAME_INVALID"


class UsernameReservedError(AuthError):
    code = "USERNAME_RESERVED"


class UsernameTakenError(AuthError):
    code = "USERNAME_TAKEN"


class PasswordTooShortError(AuthError):
    code = "PASSWORD_TOO_SHORT"


class PasswordTooLongError(AuthError):
    code = "PASSWORD_TOO_LONG"


class PasswordContainsUsernameError(AuthError):
    code = "PASSWORD_CONTAINS_USERNAME"


class PasswordTooSimpleError(AuthError):
    code = "PASSWORD_TOO_SIMPLE"


class PasswordCompromisedError(AuthError):
    code = "PASSWORD_COMPROMISED"


class InvalidCredentialsError(AuthError):
    code = "INVALID_CREDENTIALS"


class InvalidRecoveryCodeError(AuthError):
    code = "RECOVERY_CODE_INVALID"


class NotAuthenticatedError(AuthError):
    code = "NOT_AUTHENTICATED"


class TooManyAttemptsError(AuthError):
    code = "TOO_MANY_ATTEMPTS"

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(self.code)
        self.retry_after_seconds = retry_after_seconds


class DemoNotDeletableError(AuthError):
    """Una demo no tiene contraseña con la que confirmar, y se borra sola al vencer (ADR-0028)."""

    code = "DEMO_NOT_DELETABLE"


class DemoUnavailableError(AuthError):
    """Ya hay tantas demos como admite el servicio: no es culpa de quien pide."""

    code = "DEMO_UNAVAILABLE"

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(self.code)
        self.retry_after_seconds = retry_after_seconds
