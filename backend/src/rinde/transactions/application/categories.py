"""Casos de uso de categorías. Todos reciben el dueño: es el filtro de autorización."""

from datetime import datetime
from uuid import UUID, uuid4

from rinde.transactions.application.dependencies import TransactionsDependencies
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.errors import (
    CategoryInUseError,
    CategoryNameTakenError,
    CategoryNotFoundError,
)

# Categorías sembradas: el identificador es estable y la interfaz lo traduce (ADR-0011).
SEEDS: tuple[tuple[str, TransactionKind], ...] = (
    ("supermercado", TransactionKind.EXPENSE),
    ("alquiler", TransactionKind.EXPENSE),
    ("servicios", TransactionKind.EXPENSE),
    ("transporte", TransactionKind.EXPENSE),
    ("salidas", TransactionKind.EXPENSE),
    ("salud", TransactionKind.EXPENSE),
    ("otros", TransactionKind.EXPENSE),
    ("sueldo", TransactionKind.INCOME),
    ("freelance", TransactionKind.INCOME),
    ("otros-ingresos", TransactionKind.INCOME),
)


def _seed_name(slug: str) -> str:
    """Nombre de respaldo, por si la interfaz no conoce el identificador."""
    return slug.replace("-", " ").capitalize()


def _seeds_for(owner_id: UUID, at: datetime) -> list[Category]:
    return [
        Category(
            id=uuid4(),
            owner_id=owner_id,
            name=CategoryName.parse(_seed_name(slug)),
            kind=kind,
            created_at=at,
            slug=slug,
        )
        for slug, kind in SEEDS
    ]


async def _owned_category(
    deps: TransactionsDependencies, category_id: UUID, owner_id: UUID
) -> Category:
    category = await deps.categories.get(category_id, owner_id)
    if category is None:
        raise CategoryNotFoundError
    return category


class ListCategories:
    """Las del dueño. Si no tiene ninguna, las siembra en este mismo pedido (ADR-0011)."""

    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID) -> list[Category]:
        deps = self._deps
        categories = await deps.categories.list_for_owner(owner_id)
        if categories:
            return categories
        await deps.categories.add_seeds(_seeds_for(owner_id, deps.clock.now()))
        await deps.transaction.commit()
        return await deps.categories.list_for_owner(owner_id)


class CreateCategory:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, raw_name: str, kind: TransactionKind) -> Category:
        deps = self._deps
        name = CategoryName.parse(raw_name)
        if await deps.categories.find_by_name(owner_id, name.comparable, kind) is not None:
            raise CategoryNameTakenError
        category = Category(
            id=uuid4(), owner_id=owner_id, name=name, kind=kind, created_at=deps.clock.now()
        )
        await deps.categories.add(category)
        await deps.transaction.commit()
        return category


class RenameCategory:
    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, category_id: UUID, raw_name: str) -> Category:
        deps = self._deps
        category = await _owned_category(deps, category_id, owner_id)
        name = CategoryName.parse(raw_name)
        existing = await deps.categories.find_by_name(owner_id, name.comparable, category.kind)
        if existing is not None and existing.id != category.id:
            raise CategoryNameTakenError
        renamed = category.renamed(name)
        await deps.categories.save(renamed)
        await deps.transaction.commit()
        return renamed


class DeleteCategory:
    """Solo si no tiene movimientos: si no, quedarían sin clasificar (ADR-0011)."""

    def __init__(self, deps: TransactionsDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID, category_id: UUID) -> None:
        deps = self._deps
        category = await _owned_category(deps, category_id, owner_id)
        if await deps.transactions.count_by_category(category.id, owner_id) > 0:
            raise CategoryInUseError
        await deps.categories.delete(category.id, owner_id)
        await deps.transaction.commit()
