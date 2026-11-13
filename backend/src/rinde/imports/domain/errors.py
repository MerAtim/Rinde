"""Errores de importación. Cada uno lleva un código estable que la API devuelve tal cual."""

from rinde.shared.domain.errors import DomainError


class StatementImportError(DomainError):
    code = "IMPORT_ERROR"


class ImportFileTooLargeError(StatementImportError):
    """Más de lo que se acepta antes de leer (ADR-0023)."""

    code = "IMPORT_FILE_TOO_LARGE"


class ImportTooManyLinesError(StatementImportError):
    code = "IMPORT_TOO_MANY_LINES"


class ImportFileEmptyError(StatementImportError):
    """No hay ninguna línea con datos."""

    code = "IMPORT_FILE_EMPTY"


class ImportEncodingInvalidError(StatementImportError):
    """El archivo no está en la codificación elegida."""

    code = "IMPORT_ENCODING_INVALID"


class ImportLayoutInvalidError(StatementImportError):
    """Las columnas elegidas no tienen sentido: repetidas, o falta el monto."""

    code = "IMPORT_LAYOUT_INVALID"


class ImportNothingReadableError(StatementImportError):
    """Ninguna línea se pudo leer: casi siempre, columnas o separador equivocados."""

    code = "IMPORT_NOTHING_READABLE"


class ImportBatchNotFoundError(StatementImportError):
    """No existe, venció o es de otra persona: las tres se responden igual."""

    code = "IMPORT_BATCH_NOT_FOUND"


class ImportLineNotFoundError(StatementImportError):
    """La confirmación nombra una línea que el lote no tiene, o que no se pudo leer."""

    code = "IMPORT_LINE_NOT_FOUND"


class RulePatternInvalidError(StatementImportError):
    """El texto a recordar tiene menos de 3 caracteres o más de 60 (ADR-0024)."""

    code = "IMPORT_RULE_PATTERN_INVALID"


class ImportPdfInvalidError(StatementImportError):
    """No es un PDF, está dañado o tiene contraseña."""

    code = "IMPORT_PDF_INVALID"


class ImportPdfTooManyPagesError(StatementImportError):
    """Más páginas de las que tiene un resumen mensual (ADR-0023)."""

    code = "IMPORT_PDF_TOO_MANY_PAGES"


class ImportStatementUnknownError(StatementImportError):
    """El PDF no tiene la forma del resumen: otro banco, otro documento o una imagen escaneada."""

    code = "IMPORT_STATEMENT_UNKNOWN"


class ImportStatementUnbalancedError(StatementImportError):
    """Las líneas leídas no cierran con los saldos o los totales del resumen.

    Se rechaza el lote entero: una línea perdida o leída en la columna
    equivocada no se nota en la vista previa, y sí en el saldo.
    """

    code = "IMPORT_STATEMENT_UNBALANCED"


class ImportStatementMultipleAccountsError(StatementImportError):
    """El resumen trae más de una cuenta, y un lote es de una sola."""

    code = "IMPORT_STATEMENT_MULTIPLE_ACCOUNTS"


class ImportCurrencyMismatchError(StatementImportError):
    """El resumen es de una moneda y la cuenta elegida, de otra."""

    code = "IMPORT_CURRENCY_MISMATCH"
