"""Preferencias de conversión de una persona (ADR-0017).

Mientras no elija nada, ve los totales en pesos y se convierte con el MEP: es el
dólar legal al que se puede operar sin cupo, el más usado para valuar ahorros.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from rinde.preferences.domain.errors import ReferenceCurrencyNotAllowedError
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType

REFERENCE_CURRENCIES = frozenset({Currency.ARS, Currency.USD})
DEFAULT_CURRENCY = Currency.ARS
DEFAULT_RATE_TYPE = RateType.MEP


@dataclass(frozen=True, slots=True)
class Preferences:
    owner_id: UUID
    reference_currency: Currency
    rate_type: RateType
    updated_at: datetime | None = None
    """`None` mientras la persona no cambió nada: son los valores por defecto."""

    def __post_init__(self) -> None:
        if self.reference_currency not in REFERENCE_CURRENCIES:
            raise ReferenceCurrencyNotAllowedError

    @classmethod
    def defaults(cls, owner_id: UUID) -> Preferences:
        return cls(owner_id, DEFAULT_CURRENCY, DEFAULT_RATE_TYPE)
