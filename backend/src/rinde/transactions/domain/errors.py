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


class TransactionAccountNotFoundError(TransactionError):
    """La cuenta del movimiento no existe o es de otra persona: mismo código que en cuentas."""

    code = "ACCOUNT_NOT_FOUND"


class TransactionAccountArchivedError(TransactionError):
    """En una cuenta archivada no se registran movimientos nuevos (ADR-0009)."""

    code = "ACCOUNT_ARCHIVED"


class IdempotencyKeyReusedError(TransactionError):
    """La misma clave con otro contenido: quien la manda tiene un error, no un reintento."""

    code = "IDEMPOTENCY_KEY_REUSED"


class CursorInvalidError(TransactionError):
    code = "CURSOR_INVALID"


class TransferError(DomainError):
    code = "TRANSFER_ERROR"


class TransferNotFoundError(TransferError):
    """También para una transferencia ajena: no se confirma que exista (ADR-0009)."""

    code = "TRANSFER_NOT_FOUND"


class TransferSameAccountError(TransferError):
    """Mover plata de una cuenta a sí misma no es nada."""

    code = "TRANSFER_SAME_ACCOUNT"


class TransferAmountNotPositiveError(TransferError):
    """Los dos lados son positivos: la dirección la dan origen y destino (ADR-0014)."""

    code = "TRANSFER_AMOUNT_NOT_POSITIVE"


class TransferCurrencyMismatchError(TransferError):
    """Cada lado hereda la moneda de su cuenta (ADR-0014, decisión 2)."""

    code = "TRANSFER_CURRENCY_MISMATCH"


class TransferDateInFutureError(TransferError):
    code = "TRANSFER_DATE_IN_FUTURE"


class TransferDeletedError(TransferError):
    code = "TRANSFER_DELETED"


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
