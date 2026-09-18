"""La categoría: en qué se fue o de dónde vino la plata (ADR-0011)."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from rinde.shared.domain.text import is_clean, normalize
from rinde.transactions.domain.errors import CategoryNameInvalidError


class TransactionKind(StrEnum):
    """Vive acá porque una categoría también es de ingresos o de gastos."""

    INCOME = "income"
    EXPENSE = "expense"


@dataclass(frozen=True, slots=True)
class CategoryName:
    MAX_LENGTH: ClassVar[int] = 40
    value: str

    @classmethod
    def parse(cls, raw: str) -> CategoryName:
        value = normalize(raw)
        if not 1 <= len(value) <= cls.MAX_LENGTH or not is_clean(value):
            raise CategoryNameInvalidError
        return cls(value)

    @property
    def comparable(self) -> str:
        """Para detectar repetidas: "Súper" y "súper" son la misma categoría."""
        return self.value.casefold()


@dataclass(frozen=True, slots=True)
class Category:
    id: UUID
    owner_id: UUID
    name: CategoryName
    kind: TransactionKind
    created_at: datetime
    slug: str | None = None
    """Solo en las sembradas: la interfaz las traduce por este identificador (ADR-0011)."""

    @property
    def is_seeded(self) -> bool:
        return self.slug is not None

    def renamed(self, name: CategoryName) -> Category:
        # Renombrar una sembrada la vuelve propia: ya no se traduce, se muestra
        # como la escribió su dueña.
        return replace(self, name=name, slug=None)
