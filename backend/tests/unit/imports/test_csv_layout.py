"""El lector del CSV genérico (ADR-0023). Archivos inventados, con la forma de los reales."""

from datetime import date
from decimal import Decimal

import pytest

from rinde.imports.domain.csv_layout import (
    CsvLayout,
    DateOrder,
    DebitCredit,
    DecimalMark,
    Delimiter,
    Encoding,
    SignedAmount,
    parse_amount,
    parse_date,
)
from rinde.imports.domain.errors import (
    ImportEncodingInvalidError,
    ImportFileEmptyError,
    ImportFileTooLargeError,
    ImportLayoutInvalidError,
    ImportNothingReadableError,
    ImportTooManyLinesError,
)
from rinde.imports.domain.statement import (
    MAX_BYTES,
    MAX_LINES,
    LineError,
    LineProblem,
    ParsedLine,
    clean_description,
)


def layout(**changes: object) -> CsvLayout:
    values: dict[str, object] = {
        "delimiter": Delimiter.SEMICOLON,
        "encoding": Encoding.UTF8,
        "decimal_mark": DecimalMark.COMMA,
        "date_order": DateOrder.DAY_MONTH_YEAR,
        "has_header": True,
        "date_column": 0,
        "description_column": 1,
        "amount": SignedAmount(2),
    }
    values.update(changes)
    return CsvLayout(**values)  # type: ignore[arg-type]


class TestMontos:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1.234,56", "1234.56"),
            ("-1.234,56", "-1234.56"),
            ("1234,56", "1234.56"),
            ("1.234.567,8", "1234567.8"),
            ("$ 15,00", "15.00"),
            ("(1.234,56)", "-1234.56"),
            ("1.234,56-", "-1234.56"),
            ("+20", "20"),
            (" 0,55 ", "0.55"),
            ("1\u00a0234,56", "1234.56"),
        ],
    )
    def test_con_coma_decimal(self, raw: str, expected: str) -> None:
        assert parse_amount(raw, DecimalMark.COMMA) == Decimal(expected)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("1,234.56", "1234.56"), ("-1234.56", "-1234.56"), ("15", "15")],
    )
    def test_con_punto_decimal(self, raw: str, expected: str) -> None:
        assert parse_amount(raw, DecimalMark.DOT) == Decimal(expected)

    @pytest.mark.parametrize(
        "raw",
        # Separadores fuera de lugar: adivinar podría correr la coma.
        ["1.23,4", "12.34", "1,234.56", "", "abc", "1,2,3", "--5", "=1+1", "1e5"],
    )
    def test_lo_dudoso_no_se_adivina(self, raw: str) -> None:
        assert parse_amount(raw, DecimalMark.COMMA) is None


class TestFechas:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("15/10/2026", date(2026, 10, 15)),
            ("15/10/26", date(2026, 10, 15)),
            ("5-1-2026", date(2026, 1, 5)),
            ("05.01.2026", date(2026, 1, 5)),
        ],
    )
    def test_dia_mes_anio(self, raw: str, expected: date) -> None:
        assert parse_date(raw, DateOrder.DAY_MONTH_YEAR) == expected

    def test_iso(self) -> None:
        assert parse_date("2026-10-15", DateOrder.ISO) == date(2026, 10, 15)

    @pytest.mark.parametrize("raw", ["31/02/2026", "2026-10-15", "15/10", "hoy", ""])
    def test_lo_que_no_es_una_fecha(self, raw: str) -> None:
        assert parse_date(raw, DateOrder.DAY_MONTH_YEAR) is None


def test_reads_lines_skipping_the_header_and_blank_rows() -> None:
    content = (
        "Fecha;Descripción;Importe\n"
        "15/10/2026;COTO   SUC 123;-1.500,50\n"
        ";;\n"
        '16/10/2026;"TRANSF; de Ana";250.000,00\n'
    ).encode()

    statement = layout().read(content)

    assert statement.errors == []
    assert statement.lines == [
        ParsedLine(2, date(2026, 10, 15), "COTO SUC 123", Decimal("-1500.50")),
        ParsedLine(4, date(2026, 10, 16), "TRANSF; de Ana", Decimal("250000.00")),
    ]


def test_debit_and_credit_columns_give_the_sign() -> None:
    # Con coma decimal el separador va a ser punto y coma, como exporta Excel en español.
    content = (
        b"15/10/26;SEGURO HOGAR;4.321,09;\n"
        b"15/10/26;TRANSFERENCIA RECIBIDA;;98.765,43\n"
        b"16/10/26;DOS COSAS;1,00;2,00\n"
        b"16/10/26;NADA;;\n"
    )

    statement = layout(has_header=False, amount=DebitCredit(2, 3)).read(content)

    assert [(line.description, line.signed_amount) for line in statement.lines] == [
        ("SEGURO HOGAR", Decimal("-4321.09")),
        ("TRANSFERENCIA RECIBIDA", Decimal("98765.43")),
    ]
    assert statement.errors == [
        LineError(3, LineProblem.DEBIT_AND_CREDIT),
        LineError(4, LineProblem.AMOUNT_ZERO),
    ]


def test_a_bad_line_is_reported_and_the_rest_is_read() -> None:
    content = (
        b"15/10/2026;BIEN;-10,00\n"
        b"32/10/2026;FECHA MALA;-10,00\n"
        b"15/10/2026;MONTO MALO;diez\n"
        b"15/10/2026;CERO;0,00\n"
        b"15/10/2026;CORTA\n"
    )

    statement = layout(has_header=False).read(content)

    assert [line.number for line in statement.lines] == [1]
    assert statement.errors == [
        LineError(2, LineProblem.DATE_INVALID),
        LineError(3, LineProblem.AMOUNT_INVALID),
        LineError(4, LineProblem.AMOUNT_ZERO),
        LineError(5, LineProblem.COLUMNS_MISSING),
    ]


def test_a_formula_is_just_text() -> None:
    content = b'15/10/2026;=HYPERLINK("http://x");-10,00\n'

    [line] = layout(has_header=False).read(content).lines

    assert line.description == '=HYPERLINK("http://x")'


def test_windows_1252_keeps_the_accents() -> None:
    content = "15/10/2026;Panadería Ñandú;-10,00\n".encode("cp1252")

    [line] = layout(has_header=False, encoding=Encoding.WINDOWS_1252).read(content).lines

    assert line.description == "Panadería Ñandú"


def test_utf8_with_byte_order_mark() -> None:
    content = "﻿15/10/2026;Café;-10,00\n".encode()

    [line] = layout(has_header=False).read(content).lines

    assert line.occurred_on == date(2026, 10, 15)


def test_the_wrong_encoding_is_said_and_not_guessed() -> None:
    content = "15/10/2026;Panadería;-10,00\n".encode("cp1252")

    with pytest.raises(ImportEncodingInvalidError):
        layout(has_header=False).read(content)


def test_a_binary_file_is_not_a_csv() -> None:
    with pytest.raises(ImportEncodingInvalidError):
        layout().read(b"PK\x03\x04\x00\x00")


def test_an_empty_file() -> None:
    with pytest.raises(ImportFileEmptyError):
        layout().read(b"Fecha;Descripcion;Importe\n\n")


def test_nothing_readable_usually_means_the_wrong_columns() -> None:
    with pytest.raises(ImportNothingReadableError):
        layout(has_header=False).read(b"15/10/2026,COTO,-10.00\n")


def test_too_large_and_too_many_lines() -> None:
    with pytest.raises(ImportFileTooLargeError):
        layout().read(b"x" * (MAX_BYTES + 1))
    lines = "".join("15/10/2026;X;-1,00\n" for _ in range(MAX_LINES + 1)).encode()
    with pytest.raises(ImportTooManyLinesError):
        layout(has_header=False).read(lines)


@pytest.mark.parametrize(
    "changes",
    [
        {"description_column": 0},
        {"amount": SignedAmount(1)},
        {"amount": DebitCredit(2, 2)},
        {"date_column": -1},
        {"date_column": 50},
    ],
)
def test_columns_that_make_no_sense(changes: dict[str, object]) -> None:
    with pytest.raises(ImportLayoutInvalidError):
        layout(**changes)


def test_the_description_is_cleaned_not_rejected() -> None:
    assert clean_description("  COTO\t\tSUC\u200b 123  ") == "COTO SUC 123"
    assert clean_description("   ") is None
    assert clean_description("x" * 200) == "x" * 120
