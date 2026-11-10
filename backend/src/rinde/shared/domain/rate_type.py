"""Los dólares que conviven en Argentina (ADR-0002).

Está en el kernel porque lo usan varios módulos: cotizaciones lo publica y
preferencias guarda cuál elige cada persona para convertir.
"""

from enum import StrEnum


class RateType(StrEnum):
    """Los dólares que se usan en Argentina.

    `CRYPTO` es el dólar que se consigue comprando una stablecoin con pesos, no
    el precio del Bitcoin: ese es otro par de monedas.
    """

    OFFICIAL = "official"
    """Minorista de Banco Nación. No es el mayorista del BCRA (Comunicación A 3500)."""
    MEP = "mep"
    CCL = "ccl"
    BLUE = "blue"
    CARD = "card"
    CRYPTO = "crypto"


ALL_RATE_TYPES = frozenset(RateType)
