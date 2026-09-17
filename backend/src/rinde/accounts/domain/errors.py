"""Errores de cuentas. Cada uno lleva un código estable que la API devuelve tal cual."""

from rinde.shared.domain.errors import DomainError


class AccountError(DomainError):
    code = "ACCOUNT_ERROR"


class AccountNameInvalidError(AccountError):
    code = "ACCOUNT_NAME_INVALID"


class AccountCurrencyNotAllowedError(AccountError):
    """Bitcoin solo en billeteras cripto (ADR-0009)."""

    code = "ACCOUNT_CURRENCY_NOT_ALLOWED"


class AccountNotFoundError(AccountError):
    """También para una cuenta ajena: no se confirma que exista (ADR-0009)."""

    code = "ACCOUNT_NOT_FOUND"


class AccountArchivedError(AccountError):
    code = "ACCOUNT_ARCHIVED"
