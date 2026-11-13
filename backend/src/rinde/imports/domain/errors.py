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
