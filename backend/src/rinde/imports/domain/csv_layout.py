"""El CSV genérico: la persona dice cómo leerlo, y nada se adivina (ADR-0023).

Lee con el módulo `csv` de la biblioteca estándar, que sigue RFC 4180: comillas,
separadores adentro de un campo y saltos de línea entre comillas. Una celda que
empieza con "=" es texto: acá no se evalúa nada.
"""

import csv
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum

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
    Statement,
    clean_description,
)

MAX_COLUMN = 49
"""Ningún extracto tiene cincuenta columnas: un número mayor es un error de quien elige."""


class Delimiter(StrEnum):
    COMMA = ","
    SEMICOLON = ";"
    TAB = "\t"


class Encoding(StrEnum):
    UTF8 = "utf-8"
    WINDOWS_1252 = "windows-1252"
    """La de Excel en español: guarda las tildes así."""


class DecimalMark(StrEnum):
    COMMA = "comma"
    """1.234,56: la de Argentina."""
    DOT = "dot"
    """1,234.56."""


class DateOrder(StrEnum):
    DAY_MONTH_YEAR = "dmy"
    """15/10/2026 o 15/10/26."""
    ISO = "iso"
    """2026-10-15."""


@dataclass(frozen=True, slots=True)
class SignedAmount:
    """Una columna con signo: negativo es gasto."""

    column: int


@dataclass(frozen=True, slots=True)
class DebitCredit:
    """Dos columnas sin signo, como en el extracto de un banco."""

    debit: int
    credit: int


@dataclass(frozen=True, slots=True)
class CsvLayout:
    delimiter: Delimiter
    encoding: Encoding
    decimal_mark: DecimalMark
    date_order: DateOrder
    has_header: bool
    date_column: int
    description_column: int
    amount: SignedAmount | DebitCredit

    def __post_init__(self) -> None:
        columns = [self.date_column, self.description_column, *self._amount_columns()]
        if len(set(columns)) != len(columns) or any(
            column < 0 or column > MAX_COLUMN for column in columns
        ):
            raise ImportLayoutInvalidError

    def _amount_columns(self) -> list[int]:
        if isinstance(self.amount, SignedAmount):
            return [self.amount.column]
        return [self.amount.debit, self.amount.credit]

    def read(self, content: bytes) -> Statement:
        if len(content) > MAX_BYTES:
            raise ImportFileTooLargeError
        text = self._decode(content)
        lines: list[ParsedLine] = []
        errors: list[LineError] = []
        rows = csv.reader(text.splitlines(keepends=True), delimiter=self.delimiter.value)
        try:
            for index, row in enumerate(rows):
                if index == 0 and self.has_header:
                    continue
                if not any(cell.strip() for cell in row):
                    continue
                if len(lines) + len(errors) >= MAX_LINES:
                    raise ImportTooManyLinesError
                parsed = self._line(rows.line_num, row)
                if isinstance(parsed, LineError):
                    errors.append(parsed)
                else:
                    lines.append(parsed)
        except csv.Error as error:
            raise ImportNothingReadableError from error
        if not lines and not errors:
            raise ImportFileEmptyError
        if not lines:
            raise ImportNothingReadableError
        return Statement(lines, errors)

    def _decode(self, content: bytes) -> str:
        # utf-8-sig quita la marca de orden de bytes que agregan algunos programas.
        codec = "utf-8-sig" if self.encoding is Encoding.UTF8 else self.encoding.value
        try:
            text = content.decode(codec)
        except UnicodeDecodeError as error:
            raise ImportEncodingInvalidError from error
        if "\x00" in text:
            raise ImportEncodingInvalidError
        return text

    def _line(self, number: int, row: list[str]) -> ParsedLine | LineError:
        if len(row) <= max(self.date_column, self.description_column, *self._amount_columns()):
            return LineError(number, LineProblem.COLUMNS_MISSING)
        occurred_on = parse_date(row[self.date_column], self.date_order)
        if occurred_on is None:
            return LineError(number, LineProblem.DATE_INVALID)
        amount = self._amount(row)
        if isinstance(amount, LineProblem):
            return LineError(number, amount)
        return ParsedLine(
            number=number,
            occurred_on=occurred_on,
            description=clean_description(row[self.description_column]),
            signed_amount=amount,
        )

    def _amount(self, row: list[str]) -> Decimal | LineProblem:
        if isinstance(self.amount, SignedAmount):
            value = parse_amount(row[self.amount.column], self.decimal_mark)
            if value is None:
                return LineProblem.AMOUNT_INVALID
            return LineProblem.AMOUNT_ZERO if value == 0 else value
        debit = _optional_amount(row[self.amount.debit], self.decimal_mark)
        credit = _optional_amount(row[self.amount.credit], self.decimal_mark)
        if debit is None or credit is None:
            return LineProblem.AMOUNT_INVALID
        if debit and credit:
            return LineProblem.DEBIT_AND_CREDIT
        if not debit and not credit:
            return LineProblem.AMOUNT_ZERO
        # El banco escribe los dos sin signo; algunos ponen el débito con menos.
        return -abs(debit) if debit else abs(credit)


def _optional_amount(raw: str, mark: DecimalMark) -> Decimal | None:
    """Una celda vacía en débito o crédito vale cero; una ilegible, `None`."""
    if not raw.strip():
        return Decimal(0)
    return parse_amount(raw, mark)


_GROUPED = {
    DecimalMark.COMMA: re.compile(r"^(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$"),
    DecimalMark.DOT: re.compile(r"^(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$"),
}


def parse_amount(raw: str, mark: DecimalMark) -> Decimal | None:
    """Un monto como lo escribe un banco: "-1.234,56", "1234,56-", "(1.234,56)", "$ 15,00".

    Los separadores de miles tienen que estar en su lugar: "1.23,4" no es un
    número, y adivinarlo podría correr la coma.
    """
    text = raw.strip().replace("$", "").replace(" ", "").replace("\u00a0", "")
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1]
    if text.startswith("-"):
        negative, text = not negative, text[1:]
    elif text.endswith("-"):
        negative, text = not negative, text[:-1]
    elif text.startswith("+"):
        text = text[1:]
    if not _GROUPED[mark].match(text):
        return None
    thousands, decimal = (".", ",") if mark is DecimalMark.COMMA else (",", ".")
    try:
        value = Decimal(text.replace(thousands, "").replace(decimal, "."))
    except InvalidOperation:
        return None
    return -value if negative else value


_DMY = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})$")
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
CENTURY = 2000
"""Un año de dos cifras es de este siglo: los extractos son de cuentas vivas."""


def parse_date(raw: str, order: DateOrder) -> date | None:
    text = raw.strip()
    if order is DateOrder.ISO:
        match = _ISO.match(text)
        parts = (match.group(1), match.group(2), match.group(3)) if match else None
    else:
        match = _DMY.match(text)
        parts = (match.group(3), match.group(2), match.group(1)) if match else None
    if parts is None:
        return None
    year, month, day = (int(part) for part in parts)
    if year < 100:  # noqa: PLR2004  (dos cifras)
        year += CENTURY
    try:
        return date(year, month, day)
    except ValueError:
        return None
