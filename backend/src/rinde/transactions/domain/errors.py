"""Errores de movimientos. Cada uno lleva un código estable que la API devuelve tal cual."""

from rinde.shared.domain.errors import DomainError


class TransactionError(DomainError):
    code = "TRANSACTION_ERROR"


class TransactionNotFoundError(TransactionError):
    """También para un movimiento ajeno: no se confirma que exista (ADR-0009)."""

    code = "TRANSACTION_NOT_FOUND"


class TransactionAmountNotPositiveError(TransactionError):
    """El signo lo da el tipo, no el monto (ADR-0011)."""

    code = "TRANSACTION_AMOUNT_NOT_POSITIVE"


class TransactionCurrencyMismatchError(TransactionError):
    """El movimiento hereda la moneda de su cuenta (ADR-0011)."""

    code = "TRANSACTION_CURRENCY_MISMATCH"


class TransactionDateInFutureError(TransactionError):
    code = "TRANSACTION_DATE_IN_FUTURE"


class TransactionDescriptionInvalidError(TransactionError):
    code = "TRANSACTION_DESCRIPTION_INVALID"


class TransactionDeletedError(TransactionError):
    code = "TRANSACTION_DELETED"


class CategoryError(DomainError):
    code = "CATEGORY_ERROR"


class CategoryNotFoundError(CategoryError):
    code = "CATEGORY_NOT_FOUND"


class CategoryNameInvalidError(CategoryError):
    code = "CATEGORY_NAME_INVALID"


class CategoryKindMismatchError(CategoryError):
    """Una categoría de gastos no clasifica un ingreso (ADR-0011)."""

    code = "CATEGORY_KIND_MISMATCH"


class CategoryInUseError(CategoryError):
    code = "CATEGORY_IN_USE"


class CategoryNameTakenError(CategoryError):
    code = "CATEGORY_NAME_TAKEN"
