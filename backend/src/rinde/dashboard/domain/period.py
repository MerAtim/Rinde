"""El período del dashboard: meses enteros, del primero al último incluidos."""

from dataclasses import dataclass
from datetime import date, timedelta

from rinde.dashboard.domain.errors import DashboardPeriodInvalidError

DEFAULT_MONTHS = 6
"""Sin elegir nada, los últimos seis meses: alcanza para ver una tendencia."""
MAX_MONTHS = 24
"""El tope acota lo que se suma y se convierte en un pedido (ADR-0018)."""


def _shift(month: date, months: int) -> date:
    index = month.year * 12 + month.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _month_end(month: date) -> date:
    return _shift(month, 1) - timedelta(days=1)


@dataclass(frozen=True, slots=True)
class Period:
    first: date
    """El primer día del primer mes."""
    last: date
    """El primer día del último mes."""
    today: date
    """Hoy en Argentina: el mes en curso termina hoy, no a fin de mes."""

    @classmethod
    def of(cls, first: date | None, last: date | None, today: date) -> Period:
        """Si falta el último mes, es el actual; si falta el primero, cinco antes del último."""
        current = today.replace(day=1)
        last_month = last.replace(day=1) if last is not None else current
        first_month = (
            first.replace(day=1) if first is not None else _shift(last_month, -(DEFAULT_MONTHS - 1))
        )
        period = cls(first_month, last_month, today)
        if first_month > last_month or last_month > current or len(period.months) > MAX_MONTHS:
            raise DashboardPeriodInvalidError
        return period

    @property
    def months(self) -> list[date]:
        count = (self.last.year - self.first.year) * 12 + self.last.month - self.first.month + 1
        return [_shift(self.first, offset) for offset in range(count)]

    @property
    def since(self) -> date:
        return self.first

    @property
    def until(self) -> date:
        return self.closing(self.last)

    def closing(self, month: date) -> date:
        """El día que cierra el mes: el último, o hoy si es el mes en curso."""
        return min(_month_end(month), self.today)
