"""Esquemas de entrada y salida de preferencias."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from rinde.preferences.domain.preferences import Preferences
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType

# La respuesta dice en el contrato qué monedas pueden salir. La entrada acepta
# cualquier moneda y la regla la decide el dominio, con su código estable.
ReferenceCurrency = Literal["ARS", "USD"]


class PreferencesRequest(BaseModel):
    """Las dos van siempre: es reemplazar las preferencias, no parchear una."""

    model_config = ConfigDict(extra="forbid")

    reference_currency: Currency
    rate_type: RateType


class PreferencesResponse(BaseModel):
    reference_currency: ReferenceCurrency
    rate_type: RateType

    @classmethod
    def from_preferences(cls, preferences: Preferences) -> PreferencesResponse:
        currency: ReferenceCurrency = (
            "USD" if preferences.reference_currency is Currency.USD else "ARS"
        )
        return cls(reference_currency=currency, rate_type=preferences.rate_type)
