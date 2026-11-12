"""La alerta de presupuesto: un aviso cuando el gasto del mes llega a un umbral (ADR-0022).

Reglas:

* **Una vez por categoría, mes y umbral.** Si el gasto baja y vuelve a subir,
  no se repite. La base lo exige con una restricción única.
* **El aviso más fuerte incluye al otro.** Si un gasto pasa directo del 79 %
  al 120 %, avisa solo el 100 %. Y después del 100 % ya no avisa el 80 %.
* **Es una foto.** Guarda el tope y lo gastado al dispararse, en la moneda del
  tope: si después cambia el tope, la alerta sigue diciendo lo que pasó.

Los umbrales son los del presupuesto (ADR-0021): el módulo de presupuestos dice
a cuál llegó cada categoría, y acá solo se decide si hay que avisar.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from rinde.shared.domain.money import Money


class Threshold(StrEnum):
    WARNING = "warning"
    """Desde el 80 % del tope."""
    OVER = "over"
    """Desde el 100 % del tope."""


def due_threshold(reached: Threshold | None, raised: Collection[Threshold]) -> Threshold | None:
    """El umbral que hay que avisar, si hay uno.

    `reached` es el umbral al que llegó el gasto hoy; `raised`, los que ya se
    avisaron este mes para esa categoría.
    """
    if reached is None or Threshold.OVER in raised:
        return None
    if reached is Threshold.OVER:
        return Threshold.OVER
    if Threshold.WARNING in raised:
        return None
    return Threshold.WARNING


@dataclass(frozen=True, slots=True)
class BudgetAlert:
    id: UUID
    owner_id: UUID
    category_id: UUID
    month: date
    """El primer día del mes del presupuesto."""
    threshold: Threshold
    limit: Money
    spent: Money
    """En la moneda del tope, como lo midió el presupuesto al dispararse."""
    raised_at: datetime
    read_at: datetime | None = None

    def __post_init__(self) -> None:
        # Invariantes que solo rompe un error de programación, no un dato de la persona.
        if self.month.day != 1:
            msg = "el mes de una alerta es su primer día"
            raise ValueError(msg)
        if self.spent.currency is not self.limit.currency:
            msg = "lo gastado se mide en la moneda del tope"
            raise ValueError(msg)

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
