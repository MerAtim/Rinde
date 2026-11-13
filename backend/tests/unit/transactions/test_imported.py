"""Movimientos que llegan de un archivo importado (ADR-0023)."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from rinde.shared.domain.money import Currency, Money
from rinde.transactions.application.imported import ImportedLine, KnownMovement
from rinde.transactions.application.use_cases import TransactionInput
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.errors import (
    CategoryKindMismatchError,
    CategoryNotFoundError,
    TransactionAccountArchivedError,
    TransactionAccountNotFoundError,
    TransactionAlreadyImportedError,
)
from rinde.transactions.domain.transaction import AuditAction
from tests.unit.transactions.fakes import Harness, a_date

pytestmark = pytest.mark.anyio

OWNER = uuid4()
STRANGER = uuid4()


class Setup(Harness):
    def __init__(self) -> None:
        super().__init__()
        self.account_id = uuid4()
        self.accounts.add(self.account_id, OWNER)
        self.food = self._category(TransactionKind.EXPENSE, "Supermercado")
        self.salary = self._category(TransactionKind.INCOME, "Sueldo")

    def _category(self, kind: TransactionKind, name: str) -> Category:
        category = Category(
            id=uuid4(),
            owner_id=OWNER,
            name=CategoryName.parse(name),
            kind=kind,
            created_at=self.clock.now(),
        )
        self.categories.rows[category.id] = category
        return category

    def line(
        self,
        amount: str,
        fingerprint: str,
        day: int = 10,
        description: str | None = "COTO 123",
    ) -> ImportedLine:
        signed = Decimal(amount)
        return ImportedLine(
            signed_amount=signed,
            category_id=self.food.id if signed < 0 else self.salary.id,
            occurred_on=a_date(day),
            description=description,
            fingerprint=fingerprint * 64,
        )


@pytest.fixture
def setup() -> Setup:
    return Setup()


async def test_registers_expenses_and_incomes_with_their_fingerprint(setup: Setup) -> None:
    outcome = await setup.unit.register_imported.execute(
        OWNER, setup.account_id, [setup.line("-1500.50", "a"), setup.line("250000.00", "b")]
    )

    expense, income = outcome.created
    assert expense.kind is TransactionKind.EXPENSE
    assert expense.money == Money(Decimal("1500.50"), Currency.ARS)
    assert expense.source_fingerprint == "a" * 64
    assert income.kind is TransactionKind.INCOME
    assert outcome.skipped == []
    # Una sola confirmación para todo el lote, y auditoría de cada uno.
    assert setup.db.commits == 1
    assert setup.audit.actions == [AuditAction.REGISTERED, AuditAction.REGISTERED]


async def test_confirming_again_skips_what_already_entered(setup: Setup) -> None:
    lines = [setup.line("-100.00", "a"), setup.line("-200.00", "b")]
    await setup.unit.register_imported.execute(OWNER, setup.account_id, lines[:1])

    outcome = await setup.unit.register_imported.execute(OWNER, setup.account_id, lines)

    assert [item.source_fingerprint for item in outcome.created] == ["b" * 64]
    assert outcome.skipped == ["a" * 64]
    assert len(setup.transactions.rows) == 2


async def test_a_deleted_import_does_not_come_back(setup: Setup) -> None:
    [created] = (
        await setup.unit.register_imported.execute(
            OWNER, setup.account_id, [setup.line("-100.00", "a")]
        )
    ).created
    await setup.unit.delete.execute(OWNER, created.id)

    outcome = await setup.unit.register_imported.execute(
        OWNER, setup.account_id, [setup.line("-100.00", "a")]
    )

    assert outcome.created == []


async def test_the_same_fingerprint_twice_in_a_batch_enters_once(setup: Setup) -> None:
    outcome = await setup.unit.register_imported.execute(
        OWNER, setup.account_id, [setup.line("-100.00", "a"), setup.line("-100.00", "a")]
    )

    assert len(outcome.created) == 1
    assert outcome.skipped == ["a" * 64]


async def test_nothing_to_register_does_not_commit(setup: Setup) -> None:
    outcome = await setup.unit.register_imported.execute(OWNER, setup.account_id, [])

    assert outcome.created == []
    assert setup.db.commits == 0


async def test_one_invalid_line_rejects_the_whole_batch(setup: Setup) -> None:
    good = setup.line("-100.00", "a")
    # Un ingreso con una categoría de gastos.
    bad = ImportedLine(
        signed_amount=Decimal("100.00"),
        category_id=setup.food.id,
        occurred_on=a_date(10),
        description=None,
        fingerprint="b" * 64,
    )

    with pytest.raises(CategoryKindMismatchError):
        await setup.unit.register_imported.execute(OWNER, setup.account_id, [good, bad])

    assert setup.db.commits == 0
    assert setup.events.events == []


async def test_only_the_owner_can_import_into_an_account(setup: Setup) -> None:
    with pytest.raises(TransactionAccountNotFoundError):
        await setup.unit.register_imported.execute(
            STRANGER, setup.account_id, [setup.line("-100.00", "a")]
        )


async def test_a_category_of_another_person_is_not_found(setup: Setup) -> None:
    foreign = setup.line("-100.00", "a")
    foreign = ImportedLine(
        signed_amount=foreign.signed_amount,
        category_id=uuid4(),
        occurred_on=foreign.occurred_on,
        description=None,
        fingerprint=foreign.fingerprint,
    )

    with pytest.raises(CategoryNotFoundError):
        await setup.unit.register_imported.execute(OWNER, setup.account_id, [foreign])


async def test_an_archived_account_does_not_take_imports(setup: Setup) -> None:
    archived = uuid4()
    setup.accounts.add(archived, OWNER, archived=True)

    with pytest.raises(TransactionAccountArchivedError):
        await setup.unit.register_imported.execute(OWNER, archived, [setup.line("-1.00", "a")])


async def test_publishes_one_event_per_month_after_committing(setup: Setup) -> None:
    await setup.unit.register_imported.execute(
        OWNER,
        setup.account_id,
        [
            setup.line("-100.00", "a", day=1),
            setup.line("-200.00", "b", day=5),
            setup.line("300.00", "c", day=6),
        ],
    )

    # Septiembre: un solo evento, el del último gasto. El ingreso no publica.
    [event] = setup.events.events
    assert event.occurred_on == a_date(5)
    assert setup.events.commits_at_publish == [1]


async def test_a_concurrent_import_of_the_same_line_is_a_conflict(setup: Setup) -> None:
    """La consulta no la vio, pero el índice único sí (ADR-0023)."""
    await setup.unit.register_imported.execute(OWNER, setup.account_id, [setup.line("-1.00", "a")])
    original = setup.transactions.imported_fingerprints

    async def nothing(*_: object) -> set[str]:
        return set()

    setup.transactions.imported_fingerprints = nothing  # type: ignore[method-assign,assignment]
    try:
        with pytest.raises(TransactionAlreadyImportedError):
            await setup.unit.register_imported.execute(
                OWNER, setup.account_id, [setup.line("-1.00", "a")]
            )
    finally:
        setup.transactions.imported_fingerprints = original  # type: ignore[method-assign]


async def test_inspecting_tells_what_is_already_in_the_account(setup: Setup) -> None:
    await setup.unit.register_imported.execute(
        OWNER, setup.account_id, [setup.line("-100.00", "a", day=3)]
    )
    await setup.unit.register.execute(
        OWNER,
        TransactionInput(
            account_id=setup.account_id,
            kind=TransactionKind.INCOME,
            amount=Decimal("50.00"),
            category_id=setup.salary.id,
            occurred_on=a_date(15),
        ),
    )

    activity = await setup.unit.inspect_import.execute(
        OWNER, setup.account_id, ["a" * 64, "z" * 64], (date(2026, 9, 1), a_date(10))
    )

    assert activity.currency is Currency.ARS
    assert activity.imported == {"a" * 64}
    # Solo los del período: el del 15 queda afuera.
    assert activity.movements == [KnownMovement(a_date(3), Decimal("-100.00"))]


async def test_inspecting_an_account_of_another_person_is_not_found(setup: Setup) -> None:
    with pytest.raises(TransactionAccountNotFoundError):
        await setup.unit.inspect_import.execute(
            STRANGER, setup.account_id, [], (a_date(1), a_date(10))
        )
