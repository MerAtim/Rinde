"""El índice de precios al consumidor de un mes (ADR-0025).

Es el IPC nacional, nivel general, del INDEC, base diciembre de 2016. El
índice solo sirve para comparar meses entre sí: lo que importa es el cociente
entre dos índices, no el número suelto.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from enum import StrEnum

from rinde.inflation.domain.errors import CpiMonthInvalidError

INDEX_DECIMALS = 4
"""Los decimales que publica el INDEC y los de la columna `NUMERIC(14, 4)`."""

_INDEX_QUANTUM = Decimal(1).scaleb(-INDEX_DECIMALS)
# NUMERIC(14, 4) deja 10 dígitos enteros. En noviembre de 2026 el índice anda por 12.786.
_MAX_INDEX = Decimal(10) ** 10


class CpiSource(StrEnum):
    INDEC = "indec"
    """El dato es del INDEC; llega por la API de series de tiempo del Estado."""


def round_index(value: Decimal) -> Decimal:
    """Redondeo explícito para el borde: lo que llega de la fuente con más decimales."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise CpiMonthInvalidError
    try:
        return value.quantize(_INDEX_QUANTUM, rounding=ROUND_HALF_EVEN)
    except InvalidOperation:
        raise CpiMonthInvalidError from None


@dataclass(frozen=True, slots=True)
class CpiMonth:
    month: date
    """El primer día del mes al que corresponde el índice."""
    index: Decimal
    source: CpiSource

    def __post_init__(self) -> None:
        if not isinstance(self.month, date) or self.month.day != 1:
            raise CpiMonthInvalidError
        value = self.index
        if not isinstance(value, Decimal) or not value.is_finite():
            raise CpiMonthInvalidError
        if not Decimal(0) < value < _MAX_INDEX:
            raise CpiMonthInvalidError
        # Igual que con `Money`: no se redondea en silencio. Para eso está `round_index`.
        if value.quantize(_INDEX_QUANTUM) != value:
            raise CpiMonthInvalidError
