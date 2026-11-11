"""Errores de cotizaciones. Cada uno lleva un código estable que la API devuelve tal cual."""

from rinde.shared.domain.errors import DomainError


class RateError(DomainError):
    code = "RATE_ERROR"


class QuoteInvalidError(RateError):
    """Una cotización imposible: cero, negativa, con compra mayor que venta o sin zona horaria.

    Casi siempre viene de una fuente externa que respondió mal. El adaptador la
    descarta y se prueba con la fuente siguiente.
    """

    code = "QUOTE_INVALID"


class RateNotFoundError(RateError):
    """Ninguna fuente tiene ese tipo de dólar para ese día. Nunca se inventa un valor."""

    code = "RATE_NOT_FOUND"


class RatesUnavailableError(RateError):
    """Ninguna fuente respondió y no hay nada guardado: es un problema de afuera, no del pedido."""

    code = "RATES_UNAVAILABLE"


class RateDateInFutureError(RateError):
    code = "RATE_DATE_IN_FUTURE"


class ConversionNotSupportedError(RateError):
    """No hay cotización para ese par: por ahora, Bitcoin (ADR-0017)."""

    code = "CONVERSION_NOT_SUPPORTED"


class ConversionSameCurrencyError(RateError):
    """Convertir pesos a pesos no es una conversión: es un pedido mal armado."""

    code = "CONVERSION_SAME_CURRENCY"


class RateRangeInvalidError(RateError):
    """Un rango al revés o más largo de lo que se permite pedir de una vez (ADR-0018)."""

    code = "RATE_RANGE_INVALID"
