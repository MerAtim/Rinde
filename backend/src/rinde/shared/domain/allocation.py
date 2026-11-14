"""Repartos de dinero que cierran exactos: asignación por resto mayor.

Dividir $100 en 3 no da tres partes iguales al centavo. Redondear cada parte
da 3 veces 33,33 = 99,99: se pierde un centavo. Por resto mayor, cada parte se
trunca al centavo y los centavos que sobran se dan, de a uno, a las partes con
el resto más grande. La suma de las partes es siempre el total.
"""

from collections.abc import Sequence
from decimal import ROUND_DOWN, Decimal

from rinde.shared.domain.errors import DomainError
from rinde.shared.domain.money import Money


class AllocationInvalidError(DomainError):
    """Un reparto sin partes, con pesos negativos o que suman cero."""

    code = "ALLOCATION_INVALID"


def allocate(total: Money, weights: Sequence[Decimal]) -> list[Money]:
    """Reparte `total` en proporción a `weights`, en el mismo orden.

    Si dos restos empatan, gana la parte que va primero: el resultado es
    determinista. Un total negativo se reparte con el mismo signo.
    """
    if not weights or any(weight < 0 for weight in weights):
        raise AllocationInvalidError
    weight_sum = sum(weights, Decimal(0))
    if weight_sum == 0:
        raise AllocationInvalidError
    quantum = total.currency.quantum
    magnitude = abs(total.amount)
    sign = -1 if total.is_negative else 1

    exact = [magnitude * weight / weight_sum for weight in weights]
    floors = [share.quantize(quantum, rounding=ROUND_DOWN) for share in exact]
    left = int((magnitude - sum(floors, Decimal(0))) / quantum)
    by_remainder = sorted(
        range(len(weights)), key=lambda index: (-(exact[index] - floors[index]), index)
    )
    for index in by_remainder[:left]:
        floors[index] += quantum
    return [Money(sign * share, total.currency) for share in floors]


def split_equally(total: Money, parts: int) -> list[Money]:
    """Partes iguales: los centavos que sobran van a las primeras."""
    if parts < 1:
        raise AllocationInvalidError
    return allocate(total, [Decimal(1)] * parts)
