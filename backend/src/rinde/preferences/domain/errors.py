"""Errores de preferencias. Cada uno lleva un código estable que la API devuelve tal cual."""

from rinde.shared.domain.errors import DomainError


class PreferencesError(DomainError):
    code = "PREFERENCES_ERROR"


class ReferenceCurrencyNotAllowedError(PreferencesError):
    """Bitcoin no puede ser la moneda de los totales: su valor cambia cada día (ADR-0029)."""

    code = "PREFERENCES_CURRENCY_NOT_ALLOWED"
