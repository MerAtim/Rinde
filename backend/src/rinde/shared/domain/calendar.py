"""El calendario de Rinde: el día que cuenta es el de Argentina."""

from calendar import monthrange
from datetime import date, datetime
from zoneinfo import ZoneInfo

ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")


def argentine_day(moment: datetime) -> date:
    """El día en Argentina. Las fuentes publican por día argentino, no por día UTC.

    A las 22 de Buenos Aires ya es el día siguiente en UTC: con la fecha UTC se
    pediría la cotización de un día que todavía no empezó, y el mes en curso de
    un reporte terminaría antes de tiempo.
    """
    if moment.tzinfo is None:
        msg = "el momento tiene que tener zona horaria"
        raise ValueError(msg)
    return moment.astimezone(ARGENTINA).date()


def add_months(day: date, months: int) -> date:
    """El mismo día, `months` meses después. Si el mes no tiene ese día, el último.

    Se calcula siempre desde el día original: sumar de a un mes a partir del
    resultado anterior convertiría un 31 en 30 para siempre después de abril.
    """
    index = day.year * 12 + day.month - 1 + months
    year, month = index // 12, index % 12 + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))
