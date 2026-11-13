"""Lo que un lector saca de un archivo, antes de saber nada de la cuenta (ADR-0023).

Cada formato tiene su lector (patrón Strategy), y todos devuelven lo mismo:
líneas con fecha, descripción y monto con signo, y las líneas que no se
pudieron leer, con su número y el motivo. Una línea dudosa no se adivina.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

MAX_BYTES = 1024 * 1024
"""1 MB: un año de movimientos en CSV ocupa una fracción de esto."""

MAX_LINES = 2000

DESCRIPTION_LENGTH = 120
"""La misma que la de un movimiento cargado a mano."""


class LineProblem(StrEnum):
    COLUMNS_MISSING = "LINE_COLUMNS_MISSING"
    DATE_INVALID = "LINE_DATE_INVALID"
    AMOUNT_INVALID = "LINE_AMOUNT_INVALID"
    AMOUNT_ZERO = "LINE_AMOUNT_ZERO"
    DEBIT_AND_CREDIT = "LINE_DEBIT_AND_CREDIT"
    AMOUNT_TOO_PRECISE = "LINE_AMOUNT_TOO_PRECISE"
    DATE_IN_FUTURE = "LINE_DATE_IN_FUTURE"


@dataclass(frozen=True, slots=True)
class ParsedLine:
    number: int
    """El número de línea en el archivo, contando desde 1 y con el encabezado."""
    occurred_on: date
    description: str | None
    signed_amount: Decimal
    """Negativo, un gasto; positivo, un ingreso. Nunca cero."""


@dataclass(frozen=True, slots=True)
class LineError:
    number: int
    problem: LineProblem


@dataclass(frozen=True, slots=True)
class Statement:
    lines: list[ParsedLine]
    errors: list[LineError]


_SPACES = re.compile(r"\s+")


def clean_description(raw: str) -> str | None:
    """Sin caracteres invisibles, con un solo espacio entre palabras y hasta 120.

    Lo que viene del banco no se rechaza por largo ni por un carácter raro: se
    limpia, porque la persona no puede corregir el archivo del banco.
    """
    visible = "".join(
        " " if unicodedata.category(char) in {"Cc", "Cf"} else char
        for char in unicodedata.normalize("NFC", raw)
    )
    collapsed = _SPACES.sub(" ", visible).strip()
    if not collapsed:
        return None
    return collapsed[:DESCRIPTION_LENGTH].rstrip()
