"""Huellas y clasificación de las líneas de un lote (ADR-0023)."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from rinde.imports.domain.batch import (
    AccountState,
    ExistingMovement,
    LineStatus,
    classify,
    fingerprints,
)
from rinde.imports.domain.statement import LineError, LineProblem, ParsedLine, Statement
from rinde.shared.domain.money import Currency

ACCOUNT = uuid4()
TODAY = date(2026, 11, 10)


def line(number: int, amount: str, description: str = "CAFE", day: int = 5) -> ParsedLine:
    return ParsedLine(number, date(2026, 11, day), description, Decimal(amount))


def state(
    *existing: tuple[int, str],
    imported: frozenset[str] = frozenset(),
    currency: Currency = Currency.ARS,
) -> AccountState:
    return AccountState(
        currency,
        set(imported),
        [ExistingMovement(date(2026, 11, day), Decimal(amount)) for day, amount in existing],
    )


class TestHuellas:
    def test_two_equal_lines_are_two_fingerprints(self) -> None:
        first, second = fingerprints(ACCOUNT, [line(1, "-1500"), line(2, "-1500")])

        assert first != second
        assert len(first) == 64

    def test_reimporting_the_same_file_gives_the_same_fingerprints(self) -> None:
        lines = [line(1, "-1500"), line(2, "-1500"), line(3, "200")]

        assert fingerprints(ACCOUNT, lines) == fingerprints(ACCOUNT, lines)

    def test_spaces_case_and_accents_do_not_change_it(self) -> None:
        # Y tampoco el número de línea: un encabezado de más no cambia las huellas.
        assert fingerprints(ACCOUNT, [line(1, "-1500.50", "Café  Martínez")]) == fingerprints(
            ACCOUNT, [line(7, "-1500.5", "CAFE MARTINEZ")]
        )

    def test_another_account_is_another_fingerprint(self) -> None:
        assert fingerprints(ACCOUNT, [line(1, "-1")]) != fingerprints(uuid4(), [line(1, "-1")])


def test_classifies_new_duplicate_and_possible_duplicate() -> None:
    lines = [line(1, "-1500"), line(2, "-200", "OTRO"), line(3, "300", "SUELDO")]
    hashes = fingerprints(ACCOUNT, lines)
    # La primera ya entró; la segunda coincide con algo cargado a mano.
    account = state((5, "-1500"), (5, "-200"), imported=frozenset({hashes[0]}))

    result = classify(Statement(lines, []), hashes, account, TODAY)

    assert [(item.number, item.status) for item in result.lines] == [
        (1, LineStatus.DUPLICATE),
        (2, LineStatus.POSSIBLE_DUPLICATE),
        (3, LineStatus.NEW),
    ]


def test_each_existing_movement_covers_a_single_line() -> None:
    """Un café cargado a mano y dos en el archivo: el segundo es nuevo."""
    lines = [line(1, "-1500"), line(2, "-1500")]

    result = classify(
        Statement(lines, []), fingerprints(ACCOUNT, lines), state((5, "-1500")), TODAY
    )

    assert [item.status for item in result.lines] == [
        LineStatus.POSSIBLE_DUPLICATE,
        LineStatus.NEW,
    ]


def test_an_imported_line_does_not_take_the_place_of_another() -> None:
    """La línea 2 ya entró: su movimiento existente es el suyo, no el de la línea 1."""
    lines = [line(1, "-1500"), line(2, "-1500")]
    hashes = fingerprints(ACCOUNT, lines)

    result = classify(
        Statement(lines, []),
        hashes,
        state((5, "-1500"), imported=frozenset({hashes[1]})),
        TODAY,
    )

    assert [item.status for item in result.lines] == [LineStatus.NEW, LineStatus.DUPLICATE]


def test_what_the_account_cannot_take_becomes_an_error() -> None:
    lines = [line(1, "-10.555"), line(2, "-10", day=12), line(3, "-10", day=11)]
    previous = LineError(4, LineProblem.DATE_INVALID)

    result = classify(Statement(lines, [previous]), fingerprints(ACCOUNT, lines), state(), TODAY)

    # Mañana se acepta por la zona horaria; pasado mañana, no.
    assert [item.number for item in result.lines] == [3]
    assert result.errors == [
        LineError(1, LineProblem.AMOUNT_TOO_PRECISE),
        LineError(2, LineProblem.DATE_IN_FUTURE),
        previous,
    ]


def test_bitcoin_takes_eight_decimals() -> None:
    lines = [line(1, "-0.00150000")]

    result = classify(
        Statement(lines, []), fingerprints(ACCOUNT, lines), state(currency=Currency.BTC), TODAY
    )

    assert len(result.lines) == 1
