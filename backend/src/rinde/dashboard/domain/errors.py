"""Errores del dashboard. Cada uno lleva un código estable que la API devuelve tal cual."""

from rinde.shared.domain.errors import DomainError


class DashboardError(DomainError):
    code = "DASHBOARD_ERROR"


class DashboardPeriodInvalidError(DashboardError):
    """Un período al revés, que termina en el futuro o más largo que el tope (ADR-0018)."""

    code = "DASHBOARD_PERIOD_INVALID"


class DashboardConstantPricesArsOnlyError(DashboardError):
    """El IPC mide precios en pesos: con otra moneda de referencia no significa nada (ADR-0025)."""

    code = "DASHBOARD_CONSTANT_PRICES_ARS_ONLY"
