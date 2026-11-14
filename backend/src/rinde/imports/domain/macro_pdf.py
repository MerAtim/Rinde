"""El resumen de cuenta de Banco Macro en PDF (ADR-0023).

Se lee la capa de texto: cada palabra con su posición en la página. El PDF no
trae signo, así que un monto es débito o crédito según la columna donde está,
y las columnas salen del encabezado de la tabla.

Nada de eso se da por bueno sin comprobarlo. Cada línea trae el saldo que
imprime el banco, y el saldo anterior más el crédito menos el débito tiene que
dar ese saldo: un monto leído en la columna equivocada no pasa. Al final, la
suma de las líneas tiene que dar los totales del encabezado del resumen. Si
algo no cierra, se rechaza el lote entero: uno a medias es peor que ninguno.

Lo que no se sabe con certeza se rechaza en lugar de adivinarse: un renglón con
montos que no es un movimiento, una segunda cuenta en el mismo resumen o una
moneda que no se reconoce.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from rinde.imports.domain.csv_layout import DateOrder, DecimalMark, parse_amount, parse_date
from rinde.imports.domain.errors import (
    ImportFileEmptyError,
    ImportStatementMultipleAccountsError,
    ImportStatementUnbalancedError,
    ImportStatementUnknownError,
    ImportTooManyLinesError,
)
from rinde.imports.domain.statement import MAX_LINES, ParsedLine, Statement, clean_description
from rinde.shared.domain.money import Currency
from rinde.shared.domain.text import fold

MAX_PAGES = 20
"""Un resumen mensual ocupa una o dos páginas: veinte es un margen amplio (ADR-0023)."""

ROW_TOLERANCE = 2.0
"""Puntos: dos palabras del mismo renglón pueden diferir un poco en altura."""

DATE_SLACK = 12.0
"""Puntos que la fecha de un movimiento puede correrse del título "FECHA"."""


@dataclass(frozen=True, slots=True)
class Word:
    """Una palabra con su caja en la página, en puntos desde arriba a la izquierda."""

    text: str
    x0: float
    x1: float
    top: float


Page = Sequence[Word]

_MONEY = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d{2}-?$")
"""Un monto del resumen: siempre con dos decimales. Una referencia es un entero."""

_DATE = re.compile(r"^\d{2}/\d{2}/\d{2}$")

_TABLE_HEADER = ("fecha", "descripcion", "referencia", "debitos", "creditos", "saldo")
_TOTALS_HEADER = ("saldo inicial", "creditos", "debitos", "saldo final")
_TOTALS_COUNT = 5
"""Saldo inicial, créditos, débitos, IVA y saldo final, en ese orden."""

_CURRENCIES = {"pesos": Currency.ARS, "dolares": Currency.USD}


def _rows(page: Page) -> list[list[Word]]:
    """Las palabras agrupadas en renglones, de arriba abajo y de izquierda a derecha."""
    rows: list[list[Word]] = []
    for word in sorted(page, key=lambda item: (item.top, item.x0)):
        if rows and word.top - rows[-1][0].top <= ROW_TOLERANCE:
            rows[-1].append(word)
        else:
            rows.append([word])
    return [sorted(row, key=lambda item: item.x0) for row in rows]


def _text(row: Sequence[Word]) -> str:
    return " ".join(fold(word.text) for word in row)


def _money(raw: str) -> Decimal:
    value = parse_amount(raw, DecimalMark.COMMA)
    if value is None:  # pragma: no cover  (solo se llama con lo que ya pasó _MONEY)
        raise ImportStatementUnknownError
    return value


def _center(word: Word) -> float:
    return (word.x0 + word.x1) / 2


@dataclass(frozen=True, slots=True)
class _Columns:
    """Dónde termina cada zona de la tabla, sacado del encabezado de la página.

    Los montos van alineados a la derecha, así que se ubican por su borde
    derecho. El límite entre dos columnas es el punto medio entre sus títulos.
    """

    date_x0: float
    reference_x0: float
    """Lo que está a la izquierda es descripción; a la derecha, referencia."""
    debit_from: float
    credit_from: float
    balance_from: float

    @classmethod
    def from_header(cls, row: Sequence[Word]) -> _Columns | None:
        folded = [fold(word.text) for word in row]
        if folded != list(_TABLE_HEADER):
            return None
        date_word, _, reference, debit, credit, balance = row
        return cls(
            date_x0=date_word.x0,
            reference_x0=reference.x0,
            debit_from=(_center(reference) + _center(debit)) / 2,
            credit_from=(_center(debit) + _center(credit)) / 2,
            balance_from=(_center(credit) + _center(balance)) / 2,
        )


@dataclass(slots=True)
class _Amounts:
    debit: list[Decimal] = field(default_factory=list)
    credit: list[Decimal] = field(default_factory=list)
    balance: list[Decimal] = field(default_factory=list)

    def any(self) -> bool:
        return bool(self.debit or self.credit or self.balance)


def _amounts(row: Sequence[Word], columns: _Columns) -> _Amounts:
    amounts = _Amounts()
    for word in row:
        if not _MONEY.match(word.text) or word.x1 < columns.debit_from:
            continue
        value = _money(word.text)
        if word.x1 >= columns.balance_from:
            amounts.balance.append(value)
        elif word.x1 >= columns.credit_from:
            amounts.credit.append(value)
        else:
            amounts.debit.append(value)
    return amounts


@dataclass(frozen=True, slots=True)
class _Totals:
    initial: Decimal
    credits: Decimal
    debits: Decimal
    final: Decimal


@dataclass(slots=True)
class _Reader:
    """Recorre los renglones en orden y junta lo que el resumen dice de sí mismo."""

    currency: Currency | None = None
    totals: _Totals | None = None
    opening: Decimal | None = None
    closing: Decimal | None = None
    balance: Decimal | None = None
    lines: list[ParsedLine] = field(default_factory=list)
    _awaiting_totals: bool = False

    def page(self, page: Page) -> None:
        columns: _Columns | None = None
        for row in _rows(page):
            if self._awaiting_totals:
                self._read_totals(row)
                continue
            text = _text(row)
            header = _Columns.from_header(row)
            if header is not None:
                columns = header
            elif all(part in text for part in _TOTALS_HEADER):
                self._awaiting_totals = True
            elif columns is None:
                self._read_currency(text)
            else:
                self._table_row(row, text, columns)

    def _read_currency(self, text: str) -> None:
        for name, currency in _CURRENCIES.items():
            if f" en {name} " in f" {text} ":
                if self.currency not in {None, currency}:
                    raise ImportStatementMultipleAccountsError
                self.currency = currency

    def _read_totals(self, row: Sequence[Word]) -> None:
        self._awaiting_totals = False
        if self.totals is not None:
            raise ImportStatementMultipleAccountsError
        values = [word.text for word in row]
        if len(values) != _TOTALS_COUNT or not all(_MONEY.match(value) for value in values):
            raise ImportStatementUnknownError
        initial, credits, debits, _vat, final = (_money(value) for value in values)
        # El IVA no entra en la cuenta: lo que se cobra de IVA ya figura como débito.
        self.totals = _Totals(initial, credits, debits, final)

    def _table_row(self, row: Sequence[Word], text: str, columns: _Columns) -> None:
        if self.closing is not None:
            # Después del saldo final vienen impuestos informativos y leyendas,
            # con montos que no son movimientos. Solo importa si empieza otra cuenta.
            if text.startswith("saldo ultimo extracto"):
                raise ImportStatementMultipleAccountsError
            return
        amounts = _amounts(row, columns)
        if text.startswith("saldo ultimo extracto"):
            self._open(amounts)
        elif text.startswith("saldo final"):
            self._close(amounts)
        elif _DATE.match(row[0].text) and abs(row[0].x0 - columns.date_x0) <= DATE_SLACK:
            self._movement(row, amounts, columns)
        elif amounts.any():
            self._carried(amounts)
        # Un renglón sin montos que no es un movimiento (el pie legal, una
        # leyenda) no cambia nada: se deja pasar.

    def _open(self, amounts: _Amounts) -> None:
        if self.opening is not None:
            raise ImportStatementUnknownError
        self.opening = self.balance = _only_balance(amounts)

    def _close(self, amounts: _Amounts) -> None:
        if self.balance is None:
            raise ImportStatementUnknownError
        self.closing = _only_balance(amounts)

    def _carried(self, amounts: _Amounts) -> None:
        """Un saldo que se arrastra de una página a la otra tiene que ser el mismo."""
        if _only_balance(amounts) != self.balance:
            raise ImportStatementUnbalancedError

    def _movement(self, row: Sequence[Word], amounts: _Amounts, columns: _Columns) -> None:
        if self.balance is None:
            raise ImportStatementUnknownError
        if len(self.lines) >= MAX_LINES:
            raise ImportTooManyLinesError
        occurred_on = parse_date(row[0].text, DateOrder.DAY_MONTH_YEAR)
        if occurred_on is None or len(amounts.balance) != 1:
            raise ImportStatementUnknownError
        signed = _signed(amounts)
        printed = amounts.balance[0]
        if self.balance + signed != printed:
            raise ImportStatementUnbalancedError
        self.balance = printed
        description = " ".join(word.text for word in row[1:] if word.x1 <= columns.reference_x0)
        self.lines.append(
            ParsedLine(
                number=len(self.lines) + 1,
                occurred_on=occurred_on,
                description=clean_description(description),
                signed_amount=signed,
            )
        )

    def statement(self) -> Statement:
        if self.totals is None or self.opening is None or self.currency is None:
            raise ImportStatementUnknownError
        if self.closing is None:
            raise ImportStatementUnbalancedError
        debits = sum(
            (-line.signed_amount for line in self.lines if line.signed_amount < 0), Decimal(0)
        )
        credits = sum(
            (line.signed_amount for line in self.lines if line.signed_amount > 0), Decimal(0)
        )
        if (
            self.opening != self.totals.initial
            or self.closing != self.totals.final
            or self.balance != self.closing
            or debits != self.totals.debits
            or credits != self.totals.credits
        ):
            raise ImportStatementUnbalancedError
        if not self.lines:
            raise ImportFileEmptyError
        return Statement(self.lines, [], self.currency)


def _only_balance(amounts: _Amounts) -> Decimal:
    if amounts.debit or amounts.credit or len(amounts.balance) != 1:
        raise ImportStatementUnknownError
    return amounts.balance[0]


def _signed(amounts: _Amounts) -> Decimal:
    """Un movimiento trae un débito o un crédito, nunca los dos ni ninguno."""
    if len(amounts.debit) + len(amounts.credit) != 1:
        raise ImportStatementUnknownError
    value = -abs(amounts.debit[0]) if amounts.debit else abs(amounts.credit[0])
    if value == 0:
        raise ImportStatementUnknownError
    return value


def read_macro(pages: Sequence[Page]) -> Statement:
    """Las líneas del resumen, o un error si no es un resumen de Macro que cierra."""
    reader = _Reader()
    for page in pages:
        reader.page(page)
    return reader.statement()
