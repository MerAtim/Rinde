"""Reglas de categoría al importar (ADR-0024).

Una regla dice: si la descripción contiene este texto, la categoría es esta.
Se compara plegado, sin tildes, en minúsculas y con un solo espacio entre
palabras. Si coinciden varias, gana el texto más largo, que es el más
específico; a igual largo, el primero en orden alfabético.

Patrón Specification: cada regla responde si se aplica a una línea, y quien
elige entre varias no necesita saber cómo coincide cada una.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from rinde.imports.domain.errors import RulePatternInvalidError
from rinde.shared.domain.text import fold

MIN_PATTERN = 3
"""Menos que esto coincide con casi todo: "PAN" ya está en "PANAMERICANA"."""

MAX_PATTERN = 60


def comparable(text: str) -> str:
    """La forma en que se comparan descripciones y textos de regla."""
    return " ".join(fold(text).split())


def pattern_from(raw: str) -> str:
    """El texto de una regla, listo para guardar, o un error si no sirve."""
    pattern = comparable(raw)
    if not MIN_PATTERN <= len(pattern) <= MAX_PATTERN:
        raise RulePatternInvalidError
    return pattern


@dataclass(frozen=True, slots=True)
class CategoryRule:
    id: UUID
    owner_id: UUID
    pattern: str
    """Ya plegado: se guarda como se compara."""
    category_id: UUID
    is_expense: bool
    """Una regla de gastos solo se aplica a gastos, y una de ingresos, a ingresos."""
    updated_at: datetime

    def applies_to(self, description: str | None, is_expense: bool) -> bool:
        return (
            description is not None
            and self.is_expense == is_expense
            and self.pattern in comparable(description)
        )


def best_rule(
    rules: Iterable[CategoryRule], description: str | None, is_expense: bool
) -> CategoryRule | None:
    matching = [rule for rule in rules if rule.applies_to(description, is_expense)]
    if not matching:
        return None
    return min(matching, key=lambda rule: (-len(rule.pattern), rule.pattern))
