"""El lector del resumen de Macro, sobre palabras con posición (ADR-0023)."""

from datetime import date
from decimal import Decimal

import pytest

from rinde.imports.domain import macro_pdf
from rinde.imports.domain.errors import (
    ImportFileEmptyError,
    ImportStatementMultipleAccountsError,
    ImportStatementUnbalancedError,
    ImportStatementUnknownError,
    ImportTooManyLinesError,
)
from rinde.imports.domain.macro_pdf import read_macro
from rinde.imports.domain.statement import ParsedLine
from rinde.shared.domain.money import Currency
from tests.unit.imports.macro_statement import (
    BALANCE_RIGHT,
    CREDIT_RIGHT,
    DEBIT_RIGHT,
    Cell,
    MacroStatement,
    Movement,
    Row,
    balance_row,
    money,
    to_words,
    words,
)


def _row_index(page: list[Row], start: str) -> int:
    """El primer renglón que empieza con esas palabras."""
    expected = start.split(" ")
    return next(
        index
        for index, row in enumerate(page)
        if [cell.text for cell in row[: len(expected)]] == expected
    )


class TestLectura:
    def test_reads_each_movement_with_the_sign_of_its_column(self) -> None:
        statement = read_macro(to_words(MacroStatement().pages()))

        assert statement.currency is Currency.ARS
        assert statement.errors == []
        assert statement.lines == [
            ParsedLine(1, date(2026, 10, 3), "COMPRA SUPERMERCADO DEL BARRIO", Decimal("-1500.00")),
            ParsedLine(2, date(2026, 10, 5), "TRANSF RECIBIDA HABERES", Decimal("250000.00")),
            ParsedLine(3, date(2026, 10, 7), "N/D DEBITO AUTOMATICO LUZ", Decimal("-12345.67")),
        ]

    def test_the_reference_is_not_part_of_the_description(self) -> None:
        # La referencia es un número de operación: no ayuda a reconocer el gasto.
        lines = read_macro(to_words(MacroStatement().pages())).lines

        assert all("123456" not in (line.description or "") for line in lines)

    def test_a_statement_in_dollars(self) -> None:
        statement = read_macro(to_words(MacroStatement(currency="DOLARES").pages()))

        assert statement.currency is Currency.USD

    def test_several_pages_with_the_balance_carried_over(self) -> None:
        source = MacroStatement(per_page=1)

        statement = read_macro(to_words(source.pages()))

        assert len(source.pages()) == len(source.movements)
        assert [line.number for line in statement.lines] == [1, 2, 3]

    def test_a_negative_balance(self) -> None:
        source = MacroStatement(
            opening=Decimal("100.00"),
            movements=[Movement("03/10/26", "COMISION MANTENIMIENTO", Decimal("-350.50"))],
        )

        statement = read_macro(to_words(source.pages()))

        assert statement.lines[0].signed_amount == Decimal("-350.50")

    def test_amounts_after_the_final_balance_are_not_movements(self) -> None:
        # Debajo del saldo final, el banco informa impuestos cobrados en el mes.
        source = MacroStatement(
            after_closing=[
                [*words("TOTAL COBRADO DEL IMPUESTO", 46), Cell("0,00", BALANCE_RIGHT, right=True)],
                [*words("RECAUDADO EN EL MES", 46), Cell("8.000,00", BALANCE_RIGHT, right=True)],
            ]
        )

        assert len(read_macro(to_words(source.pages())).lines) == len(source.movements)


class TestControles:
    def test_an_amount_in_the_wrong_column_does_not_close(self) -> None:
        pages = MacroStatement().pages()
        row = pages[0][_row_index(pages[0], "03/10/26")]
        # El débito de 1.500,00 leído como crédito: el saldo impreso lo delata.
        row[-2] = Cell(row[-2].text, CREDIT_RIGHT, right=True)

        with pytest.raises(ImportStatementUnbalancedError):
            read_macro(to_words(pages))

    def test_a_missing_line_does_not_close(self) -> None:
        pages = MacroStatement().pages()
        del pages[0][_row_index(pages[0], "05/10/26")]

        with pytest.raises(ImportStatementUnbalancedError):
            read_macro(to_words(pages))

    def test_totals_that_do_not_match_the_lines(self) -> None:
        source = MacroStatement()
        initial, credits, debits, final = source.header_totals()
        source.totals = (initial, credits + 1, debits + 1, final)

        with pytest.raises(ImportStatementUnbalancedError):
            read_macro(to_words(source.pages()))

    def test_an_opening_balance_different_from_the_header(self) -> None:
        source = MacroStatement()
        initial, credits, debits, final = source.header_totals()
        source.totals = (initial + 1, credits, debits, final + 1)

        with pytest.raises(ImportStatementUnbalancedError):
            read_macro(to_words(source.pages()))

    def test_a_carried_balance_that_changed(self) -> None:
        pages = MacroStatement(per_page=1).pages()
        carried = _row_index(pages[1], "SALDO ANTERIOR")
        pages[1][carried] = balance_row("SALDO ANTERIOR", Decimal("1.00"))

        with pytest.raises(ImportStatementUnbalancedError):
            read_macro(to_words(pages))

    def test_without_the_final_balance(self) -> None:
        pages = MacroStatement().pages()
        del pages[0][_row_index(pages[0], "SALDO FINAL AL")]

        with pytest.raises(ImportStatementUnbalancedError):
            read_macro(to_words(pages))


class TestFormaDesconocida:
    def test_a_scanned_statement_has_no_text(self) -> None:
        with pytest.raises(ImportStatementUnknownError):
            read_macro([[]])

    def test_without_the_table_header(self) -> None:
        pages = MacroStatement().pages()
        del pages[0][_row_index(pages[0], "FECHA")]

        with pytest.raises(ImportStatementUnknownError):
            read_macro(to_words(pages))

    def test_without_a_known_currency(self) -> None:
        with pytest.raises(ImportStatementUnknownError):
            read_macro(to_words(MacroStatement(currency="EUROS").pages()))

    def test_a_movement_with_debit_and_credit(self) -> None:
        pages = MacroStatement().pages()
        row = pages[0][_row_index(pages[0], "03/10/26")]
        row.insert(-1, Cell("1,00", CREDIT_RIGHT, right=True))

        with pytest.raises(ImportStatementUnknownError):
            read_macro(to_words(pages))

    def test_a_movement_without_a_balance(self) -> None:
        pages = MacroStatement().pages()
        row = pages[0][_row_index(pages[0], "03/10/26")]
        row.pop()

        with pytest.raises(ImportStatementUnknownError):
            read_macro(to_words(pages))

    def test_a_row_with_a_debit_that_is_not_a_movement(self) -> None:
        pages = MacroStatement().pages()
        at = _row_index(pages[0], "05/10/26")
        pages[0].insert(at, [*words("SIN FECHA", 80), Cell("10,00", DEBIT_RIGHT, right=True)])

        with pytest.raises(ImportStatementUnknownError):
            read_macro(to_words(pages))

    def test_a_movement_of_zero(self) -> None:
        pages = MacroStatement().pages()
        at = _row_index(pages[0], "05/10/26")
        balance = MacroStatement().balances()[0]
        pages[0].insert(
            at,
            [
                Cell("04/10/26", 37),
                *words("AJUSTE", 80),
                Cell("0,00", DEBIT_RIGHT, right=True),
                Cell(money(balance), BALANCE_RIGHT, right=True),
            ],
        )

        with pytest.raises(ImportStatementUnknownError):
            read_macro(to_words(pages))

    def test_a_movement_before_the_opening_balance(self) -> None:
        pages = MacroStatement().pages()
        del pages[0][_row_index(pages[0], "SALDO ULTIMO")]

        with pytest.raises(ImportStatementUnknownError):
            read_macro(to_words(pages))

    def test_a_final_balance_without_an_opening_one(self) -> None:
        pages = MacroStatement(movements=[]).pages()
        del pages[0][_row_index(pages[0], "SALDO ULTIMO")]

        with pytest.raises(ImportStatementUnknownError):
            read_macro(to_words(pages))

    def test_a_date_that_does_not_exist(self) -> None:
        pages = MacroStatement().pages()
        row = pages[0][_row_index(pages[0], "03/10/26")]
        row[0] = Cell("31/02/26", row[0].x)

        with pytest.raises(ImportStatementUnknownError):
            read_macro(to_words(pages))

    def test_totals_with_a_missing_value(self) -> None:
        pages = MacroStatement().pages()
        pages[0][_row_index(pages[0], "SALDO INICIAL") + 1].pop()

        with pytest.raises(ImportStatementUnknownError):
            read_macro(to_words(pages))


class TestUnaSolaCuenta:
    def test_a_second_account_after_the_first(self) -> None:
        first = MacroStatement().pages()
        second = MacroStatement(currency="DOLARES").pages()

        with pytest.raises(ImportStatementMultipleAccountsError):
            read_macro(to_words([*first, *second]))

    def test_a_second_account_in_the_same_currency(self) -> None:
        pages = MacroStatement().pages()

        with pytest.raises(ImportStatementMultipleAccountsError):
            read_macro(to_words([*pages, *MacroStatement().pages()]))

    def test_another_account_below_the_final_balance(self) -> None:
        source = MacroStatement(
            after_closing=[balance_row("SALDO ULTIMO EXTRACTO AL 30/09/2026", Decimal("1.00"))]
        )

        with pytest.raises(ImportStatementMultipleAccountsError):
            read_macro(to_words(source.pages()))

    def test_a_second_opening_balance_in_the_same_table(self) -> None:
        pages = MacroStatement().pages()
        pages[0].insert(
            _row_index(pages[0], "05/10/26"),
            balance_row("SALDO ULTIMO EXTRACTO AL 30/09/2026", Decimal("1.00")),
        )

        with pytest.raises(ImportStatementUnknownError):
            read_macro(to_words(pages))


class TestLimites:
    def test_no_movements_is_an_empty_file(self) -> None:
        with pytest.raises(ImportFileEmptyError):
            read_macro(to_words(MacroStatement(movements=[]).pages()))

    def test_too_many_movements(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(macro_pdf, "MAX_LINES", 2)

        with pytest.raises(ImportTooManyLinesError):
            read_macro(to_words(MacroStatement().pages()))
