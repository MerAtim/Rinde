"""Conversión de muchos montos, cada uno con la cotización de su día (ADR-0018, ADR-0029)."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from rinde.rates.application.use_cases import GetQuoteSeries, RatesDependencies, kinds_for
from rinde.rates.domain.conversion import convert_exact
from rinde.rates.domain.quote import Market, Quote, QuoteKind
from rinde.shared.domain.money import Currency, Money
from rinde.shared.domain.rate_type import RateType


@dataclass(frozen=True, slots=True)
class DayConverter:
    """Lleva montos a una moneda con la cotización de cada día de series ya traídas.

    No sale a buscar nada: es una función pura sobre las series, así que
    convertir mil montos no hace mil consultas. Tiene una serie por clase que
    hace falta: el dólar elegido y, si hay Bitcoin, su precio.
    """

    target: Currency
    rate_type: RateType
    series: dict[QuoteKind, dict[date, Quote]] = field(default_factory=dict)

    def supports(self, currency: Currency) -> bool:
        """Si esa moneda se puede llevar a la de destino con las series que se trajeron.

        Una serie vacía (la fuente no respondió y no había nada guardado) es como
        no tenerla: esa moneda se informa aparte y los totales del resto siguen
        en pie. Un día suelto sin cotización es otra cosa: lo resuelve `to_target`.
        """
        return all(
            self.series.get(kind) for kind in kinds_for(currency, self.target, self.rate_type)
        )

    def to_target(self, money: Money, day: date) -> Decimal | None:
        """El monto en la moneda de destino, sin redondear. `None` si falta una cotización ese día.

        Sigue la regla prudente de ADR-0017 en cada paso: el signo del monto dice
        si es algo que se tiene o algo que se debe.
        """
        if money.currency is self.target:
            return money.amount
        quotes = []
        for kind in kinds_for(money.currency, self.target, self.rate_type):
            quote = self.series.get(kind, {}).get(day)
            if quote is None:
                return None
            quotes.append(quote)
        return convert_exact(money, *quotes).amount


class GetConverter:
    """Las series de un rango, listas para convertir montos de esos días.

    Se traen solo las que hacen falta para las monedas pedidas: quien no tiene
    Bitcoin no espera al precio del Bitcoin.
    """

    def __init__(self, deps: RatesDependencies) -> None:
        self._series = GetQuoteSeries(deps)

    async def execute(
        self,
        target: Currency,
        rate_type: RateType,
        since: date,
        until: date,
        currencies: frozenset[Currency] = frozenset({Currency.ARS, Currency.USD}),
    ) -> DayConverter:
        needed: set[QuoteKind] = set()
        for currency in currencies - {target}:
            needed.update(kinds_for(currency, target, rate_type))
        # Siempre en el mismo orden: el dólar primero, después los mercados.
        ordered = sorted(needed, key=lambda kind: isinstance(kind, Market))
        series = {kind: await self._series.execute(kind, since, until) for kind in ordered}
        return DayConverter(target, rate_type, series)
