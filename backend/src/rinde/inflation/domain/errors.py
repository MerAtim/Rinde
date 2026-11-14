"""Errores de inflación. Cada uno lleva un código estable."""

from rinde.shared.domain.errors import DomainError


class InflationError(DomainError):
    code = "INFLATION_ERROR"


class CpiMonthInvalidError(InflationError):
    """Un índice imposible: cero, negativo, con más decimales o fuera del primer día del mes.

    Casi siempre viene de la fuente. El adaptador lo descarta y sigue con el resto.
    """

    code = "CPI_MONTH_INVALID"


class CpiRangeInvalidError(InflationError):
    """Un rango de meses al revés."""

    code = "CPI_RANGE_INVALID"
