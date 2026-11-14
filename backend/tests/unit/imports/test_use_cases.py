"""Casos de uso de importación, con movimientos en memoria (ADR-0023)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from rinde.imports.application.ports import CategoryInfo
from rinde.imports.application.unit import ImportsGateways, build_imports_unit
from rinde.imports.application.use_cases import BatchPreview, Choice
from rinde.imports.domain.batch import AccountState, ExistingMovement, LineStatus
from rinde.imports.domain.csv_layout import (
    CsvLayout,
    DateOrder,
    DecimalMark,
    Delimiter,
    Encoding,
    SignedAmount,
)
from rinde.imports.domain.errors import (
    ImportBatchNotFoundError,
    ImportCurrencyMismatchError,
    ImportFileTooLargeError,
    ImportLineNotFoundError,
    RulePatternInvalidError,
)
from rinde.imports.domain.rules import CategoryRule
from rinde.imports.domain.statement import MAX_BYTES, LineError, LineProblem
from rinde.imports.infrastructure.pdf import PdfPlumberText
from rinde.shared.domain.money import Currency
from tests.fakes import FakeClock, FakeTransaction
from tests.unit.imports.fakes import (
    FakeAccount,
    FixedCategories,
    InMemoryBatchRepository,
    InMemoryRuleRepository,
)
from tests.unit.imports.macro_statement import MacroStatement, to_pdf

pytestmark = pytest.mark.anyio

OWNER = uuid4()
STRANGER = uuid4()
ACCOUNT = uuid4()
# Las 12 de Buenos Aires del 10 de noviembre de 2026.
NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)
OTHER_EXPENSES = CategoryInfo(uuid4(), "otros", is_expense=True)
OTHER_INCOMES = CategoryInfo(uuid4(), "otros-ingresos", is_expense=False)
FOOD = CategoryInfo(uuid4(), "supermercado", is_expense=True)

LAYOUT = CsvLayout(
    delimiter=Delimiter.SEMICOLON,
    encoding=Encoding.UTF8,
    decimal_mark=DecimalMark.COMMA,
    date_order=DateOrder.DAY_MONTH_YEAR,
    has_header=True,
    date_column=0,
    description_column=1,
    amount=SignedAmount(2),
)

FILE = (
    "Fecha;Descripción;Importe\n"
    "03/11/2026;COTO;-1.500,00\n"
    "05/11/2026;SUELDO;250.000,00\n"
    "06/11/2026;CAFE;-900,00\n"
    "07/11/2026;MAL;diez\n"
).encode()


class Setup:
    def __init__(self) -> None:
        self.clock = FakeClock()
        self.clock.current = NOW
        self.batches = InMemoryBatchRepository()
        self.rules = InMemoryRuleRepository()
        self.db = FakeTransaction()
        # El café ya está cargado a mano.
        self.account = FakeAccount(
            OWNER,
            ACCOUNT,
            AccountState(
                Currency.ARS, set(), [ExistingMovement(date(2026, 11, 6), Decimal("-900.00"))]
            ),
        )
        self.unit = build_imports_unit(
            self.batches,
            self.rules,
            self.db,
            ImportsGateways(
                accounts=self.account,
                registrar=self.account,
                categories=FixedCategories(OWNER, OTHER_EXPENSES, OTHER_INCOMES, FOOD),
                pdf=PdfPlumberText(),
            ),
            self.clock,
        )

    async def upload(self, content: bytes = FILE, owner_id: UUID = OWNER) -> BatchPreview:
        return await self.unit.create.execute(
            owner_id, ACCOUNT, "  extracto   octubre.csv ", content, LAYOUT
        )


@pytest.fixture
def setup() -> Setup:
    return Setup()


async def test_uploading_reads_classifies_and_suggests(setup: Setup) -> None:
    preview = await setup.upload()
    batch = preview.batch

    assert batch.file_name == "extracto octubre.csv"
    assert len(batch.file_sha256) == 64
    assert [(line.number, line.status) for line in batch.lines] == [
        (2, LineStatus.NEW),
        (3, LineStatus.NEW),
        (4, LineStatus.POSSIBLE_DUPLICATE),
    ]
    assert batch.errors == [LineError(5, LineProblem.AMOUNT_INVALID)]
    # Cada línea arranca en "otros" de su tipo.
    assert {number: item.category_id for number, item in preview.suggestions.items()} == {
        2: OTHER_EXPENSES.id,
        3: OTHER_INCOMES.id,
        4: OTHER_EXPENSES.id,
    }
    # Se pregunta por la cuenta solo en el período del archivo.
    assert setup.account.periods == [(date(2026, 11, 3), date(2026, 11, 6))]
    assert setup.db.commits == 1
    assert batch.expires_at == NOW + timedelta(hours=24)


class TestResumenPdf:
    async def test_the_macro_statement_is_read_with_its_own_reader(self, setup: Setup) -> None:
        source = MacroStatement()

        preview = await setup.unit.create.execute(
            OWNER, ACCOUNT, "resumen.pdf", to_pdf(source.pages()), setup.unit.macro_pdf
        )

        assert [line.signed_amount for line in preview.batch.lines] == [
            movement.amount for movement in source.movements
        ]
        assert preview.batch.errors == []

    async def test_a_statement_in_another_currency_is_not_saved(self, setup: Setup) -> None:
        content = to_pdf(MacroStatement(currency="DOLARES").pages())

        with pytest.raises(ImportCurrencyMismatchError):
            await setup.unit.create.execute(
                OWNER, ACCOUNT, "resumen.pdf", content, setup.unit.macro_pdf
            )

        assert setup.batches.rows == {}
        assert setup.db.commits == 0


async def test_confirming_registers_the_chosen_lines(setup: Setup) -> None:
    batch = (await setup.upload()).batch

    result = await setup.unit.confirm.execute(
        OWNER, batch.id, [Choice(2, FOOD.id), Choice(3, OTHER_INCOMES.id)]
    )

    assert (result.imported, result.skipped) == (2, 0)
    assert [(item.signed_amount, item.category_id) for item in setup.account.registered] == [
        (Decimal("-1500.00"), FOOD.id),
        (Decimal("250000.00"), OTHER_INCOMES.id),
    ]
    stored = setup.batches.rows[batch.id]
    assert stored.confirmed_at == NOW
    assert (stored.imported, stored.skipped) == (2, 0)


async def test_confirming_again_returns_the_same_and_does_not_register(setup: Setup) -> None:
    batch = (await setup.upload()).batch
    await setup.unit.confirm.execute(OWNER, batch.id, [Choice(2, FOOD.id)])

    again = await setup.unit.confirm.execute(OWNER, batch.id, [Choice(3, FOOD.id)])

    assert (again.imported, again.skipped) == (1, 0)
    assert len(setup.account.registered) == 1


async def test_a_second_batch_of_the_same_file_marks_duplicates(setup: Setup) -> None:
    first = (await setup.upload()).batch
    await setup.unit.confirm.execute(OWNER, first.id, [Choice(2, FOOD.id)])

    second = (await setup.upload()).batch

    assert [line.status for line in second.lines] == [
        LineStatus.DUPLICATE,
        LineStatus.NEW,
        LineStatus.POSSIBLE_DUPLICATE,
    ]
    # Un duplicado elegido igual no se manda.
    result = await setup.unit.confirm.execute(OWNER, second.id, [Choice(2, FOOD.id)])
    assert (result.imported, result.skipped) == (0, 0)


async def test_a_line_that_does_not_exist_or_could_not_be_read(setup: Setup) -> None:
    batch = (await setup.upload()).batch

    for number in (5, 99):
        with pytest.raises(ImportLineNotFoundError):
            await setup.unit.confirm.execute(OWNER, batch.id, [Choice(number, FOOD.id)])
    assert setup.account.registered == []


async def test_nobody_sees_confirms_or_discards_the_batch_of_another(setup: Setup) -> None:
    batch = (await setup.upload()).batch

    with pytest.raises(ImportBatchNotFoundError):
        await setup.unit.get.execute(STRANGER, batch.id)
    with pytest.raises(ImportBatchNotFoundError):
        await setup.unit.confirm.execute(STRANGER, batch.id, [])
    with pytest.raises(ImportBatchNotFoundError):
        await setup.unit.discard.execute(STRANGER, batch.id)
    assert batch.id in setup.batches.rows


async def test_an_expired_batch_is_gone(setup: Setup) -> None:
    batch = (await setup.upload()).batch
    setup.clock.current = NOW + timedelta(hours=24)

    with pytest.raises(ImportBatchNotFoundError):
        await setup.unit.get.execute(OWNER, batch.id)
    # Y el próximo lote lo limpia.
    await setup.upload()
    assert batch.id not in setup.batches.rows


async def test_a_confirmed_batch_does_not_expire_nor_can_be_discarded(setup: Setup) -> None:
    batch = (await setup.upload()).batch
    await setup.unit.confirm.execute(OWNER, batch.id, [])
    setup.clock.current = NOW + timedelta(days=30)

    assert (await setup.unit.get.execute(OWNER, batch.id)).batch.confirmed_at == NOW
    with pytest.raises(ImportBatchNotFoundError):
        await setup.unit.discard.execute(OWNER, batch.id)


async def test_discarding_a_pending_batch(setup: Setup) -> None:
    batch = (await setup.upload()).batch

    await setup.unit.discard.execute(OWNER, batch.id)

    assert setup.batches.rows == {}


async def test_too_large_is_rejected_before_reading(setup: Setup) -> None:
    with pytest.raises(ImportFileTooLargeError):
        await setup.upload(b"x" * (MAX_BYTES + 1))
    assert setup.batches.rows == {}


async def test_an_account_of_another_person_is_rejected_by_movements(setup: Setup) -> None:
    with pytest.raises(LookupError):
        await setup.upload(owner_id=STRANGER)


class TestReglas:
    """Reglas de categoría al confirmar y al proponer (ADR-0024)."""

    async def test_remembering_saves_a_rule_that_the_next_batch_uses(self, setup: Setup) -> None:
        batch = (await setup.upload()).batch
        await setup.unit.confirm.execute(OWNER, batch.id, [Choice(2, FOOD.id, remember=" Coto ")])

        preview = await setup.upload()

        [saved] = setup.rules.rows
        assert (saved.pattern, saved.category_id, saved.is_expense) == ("coto", FOOD.id, True)
        assert preview.suggestions[2].category_id == FOOD.id
        assert preview.suggestions[2].rule == "coto"
        # Las que no coinciden siguen en "otros", sin regla.
        assert preview.suggestions[4].category_id == OTHER_EXPENSES.id
        assert preview.suggestions[4].rule is None

    async def test_remembering_the_same_text_replaces_the_category(self, setup: Setup) -> None:
        first = (await setup.upload()).batch
        await setup.unit.confirm.execute(OWNER, first.id, [Choice(2, FOOD.id, remember="coto")])
        second = (await setup.upload()).batch

        await setup.unit.confirm.execute(
            OWNER, second.id, [Choice(2, OTHER_EXPENSES.id, remember="COTO")]
        )

        [saved] = setup.rules.rows
        assert saved.category_id == OTHER_EXPENSES.id

    async def test_an_invalid_text_rejects_before_registering(self, setup: Setup) -> None:
        batch = (await setup.upload()).batch

        with pytest.raises(RulePatternInvalidError):
            await setup.unit.confirm.execute(
                OWNER, batch.id, [Choice(2, FOOD.id), Choice(3, OTHER_INCOMES.id, remember="ab")]
            )

        assert setup.account.registered == []
        assert setup.rules.rows == []
        assert setup.batches.rows[batch.id].confirmed_at is None

    async def test_the_rule_takes_the_kind_of_its_line(self, setup: Setup) -> None:
        batch = (await setup.upload()).batch

        await setup.unit.confirm.execute(
            OWNER, batch.id, [Choice(3, OTHER_INCOMES.id, remember="sueldo")]
        )

        [saved] = setup.rules.rows
        assert saved.is_expense is False

    async def test_rules_of_another_person_are_not_used(self, setup: Setup) -> None:
        setup.rules.rows.append(
            CategoryRule(uuid4(), STRANGER, "coto", FOOD.id, is_expense=True, updated_at=NOW)
        )

        preview = await setup.upload()

        assert preview.suggestions[2].rule is None
