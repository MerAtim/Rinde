"""Conversión de muchos montos, cada uno con la cotización de su día (ADR-0018)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from rinde.rates.application.use_cases import CONVERTIBLE, GetQuoteSeries, RatesDependencies
from rinde.rates.domain.conversion import convert_exact
from rinde.rates.domain.quote import Quote
from rinde.shared.domain.money import Currency, Money
from rinde.shared.domain.rate_type import RateType


@dataclass(frozen=True, slots=True)
class DayConverter:
    """Lleva montos a una moneda con la cotización de cada día de una serie ya traída.

    No sale a buscar nada: es una función pura sobre la serie, así que convertir
    mil montos no hace mil consultas.
    """

    target: Currency
    series: dict[date, Quote]

    def supports(self, currency: Currency) -> bool:
        """Si esa moneda se puede llevar a la de destino. Bitcoin, todavía no (ADR-0017)."""
        return currency is self.target or (currency in CONVERTIBLE and self.target in CONVERTIBLE)

    def to_target(self, money: Money, day: date) -> Decimal | None:
        """El monto en la moneda de destino, sin redondear. `None` si ese día no tiene cotización.

        Sigue la regla prudente de ADR-0017: el signo del monto dice si es algo
        que se tiene o algo que se debe.
        """
        if money.currency is self.target:
            return money.amount
        if not self.supports(money.currency):
            return None
        quote = self.series.get(day)
        if quote is None:
            return None
        return convert_exact(money, quote).amount


class GetConverter:
    """La serie de un dólar para un rango, lista para convertir montos de esos días."""

    def __init__(self, deps: RatesDependencies) -> None:
        self._series = GetQuoteSeries(deps)

    async def execute(
        self, target: Currency, rate_type: RateType, since: date, until: date
    ) -> DayConverter:
        return DayConverter(target, await self._series.execute(rate_type, since, until))
