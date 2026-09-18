"""Casos de uso de categorías (ADR-0011)."""

from decimal import Decimal
from uuid import uuid4

import pytest

from rinde.transactions.application.categories import SEEDS
from rinde.transactions.application.use_cases import TransactionInput
from rinde.transactions.domain.category import TransactionKind
from rinde.transactions.domain.errors import (
    CategoryInUseError,
    CategoryNameInvalidError,
    CategoryNameTakenError,
    CategoryNotFoundError,
)
from tests.unit.transactions.fakes import Harness, a_date

pytestmark = pytest.mark.anyio

OWNER = uuid4()
STRANGER = uuid4()


@pytest.fixture
def setup() -> Harness:
    return Harness()


async def test_the_first_time_they_are_asked_they_are_seeded(setup: Harness) -> None:
    unit = setup.unit

    seeded = await unit.categories.execute(OWNER)

    assert len(seeded) == len(SEEDS)
    assert {category.slug for category in seeded} == {slug for slug, _ in SEEDS}
    assert all(category.owner_id == OWNER for category in seeded)


async def test_seeding_happens_once(setup: Harness) -> None:
    unit, categories = setup.unit, setup.categories

    first = await unit.categories.execute(OWNER)
    second = await unit.categories.execute(OWNER)

    assert [category.id for category in first] == [category.id for category in second]
    assert len(categories.rows) == len(SEEDS)


async def test_each_person_gets_their_own(setup: Harness) -> None:
    unit = setup.unit

    mine = await unit.categories.execute(OWNER)
    theirs = await unit.categories.execute(STRANGER)

    assert {category.id for category in mine}.isdisjoint({category.id for category in theirs})


async def test_a_new_category_cannot_repeat_a_name_of_the_same_kind(setup: Harness) -> None:
    unit = setup.unit
    await unit.create_category.execute(OWNER, "Mascotas", TransactionKind.EXPENSE)

    with pytest.raises(CategoryNameTakenError):
        # Distinta escritura, misma categoría.
        await unit.create_category.execute(OWNER, "  mascotas ", TransactionKind.EXPENSE)

    # El mismo nombre para ingresos sí se admite: son listas distintas.
    assert await unit.create_category.execute(OWNER, "Mascotas", TransactionKind.INCOME)


async def test_an_empty_name_is_rejected(setup: Harness) -> None:
    unit = setup.unit

    with pytest.raises(CategoryNameInvalidError):
        await unit.create_category.execute(OWNER, "   ", TransactionKind.EXPENSE)


async def test_renaming_a_seeded_one_makes_it_personal(setup: Harness) -> None:
    unit = setup.unit
    seeded = await unit.categories.execute(OWNER)
    market = next(category for category in seeded if category.slug == "supermercado")

    renamed = await unit.rename_category.execute(OWNER, market.id, "Chino de la esquina")

    assert renamed.name.value == "Chino de la esquina"
    assert renamed.slug is None


async def test_a_category_of_another_person_is_not_found(setup: Harness) -> None:
    unit = setup.unit
    mine = await unit.create_category.execute(OWNER, "Mascotas", TransactionKind.EXPENSE)

    with pytest.raises(CategoryNotFoundError):
        await unit.rename_category.execute(STRANGER, mine.id, "Robada")
    with pytest.raises(CategoryNotFoundError):
        await unit.delete_category.execute(STRANGER, mine.id)


async def test_a_category_with_movements_is_not_deleted(setup: Harness) -> None:
    unit, categories, accounts = setup.unit, setup.categories, setup.accounts
    account_id = uuid4()
    accounts.add(account_id, OWNER)
    category = await unit.create_category.execute(OWNER, "Mascotas", TransactionKind.EXPENSE)
    await unit.register.execute(
        OWNER,
        TransactionInput(
            account_id=account_id,
            kind=TransactionKind.EXPENSE,
            amount=Decimal("1200.00"),
            category_id=category.id,
            occurred_on=a_date(),
        ),
    )

    with pytest.raises(CategoryInUseError):
        await unit.delete_category.execute(OWNER, category.id)
    assert category.id in categories.rows


async def test_a_category_without_movements_is_deleted(setup: Harness) -> None:
    unit, categories = setup.unit, setup.categories
    category = await unit.create_category.execute(OWNER, "Mascotas", TransactionKind.EXPENSE)

    await unit.delete_category.execute(OWNER, category.id)

    assert category.id not in categories.rows
