"""Un resumen de Banco Macro inventado, para probar el lector sin datos reales.

Copia la geometría del resumen (dónde va cada columna), no su contenido: las
descripciones, montos y números de cuenta son inventados. Sale como palabras,
para el dominio, o como un PDF de verdad, para el adaptador. Se escribe en
Courier, de ancho fijo, así el ancho de cada palabra se calcula sin métricas.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from rinde.imports.domain.macro_pdf import Word

FONT_SIZE = 8
CHAR_WIDTH = 0.6 * FONT_SIZE
"""Courier: cada carácter mide 600 milésimas del tamaño de la letra."""

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
ROW_HEIGHT = 12

# Dónde empieza (izquierda) o termina (derecha) cada cosa, en puntos.
DATE_X = 37
DESCRIPTION_X = 80
"""Courier es más ancha que la letra del banco: la fecha termina en 75."""
REFERENCE_X = 268
DEBIT_RIGHT = 382
CREDIT_RIGHT = 461
BALANCE_RIGHT = 558


@dataclass(frozen=True, slots=True)
class Cell:
    text: str
    x: float
    right: bool = False
    """Si `x` es el borde derecho: los montos van alineados a la derecha."""

    @property
    def x0(self) -> float:
        return self.x - self.width if self.right else self.x

    @property
    def width(self) -> float:
        return len(self.text) * CHAR_WIDTH


Row = list[Cell]


def money(value: Decimal) -> str:
    """Como lo imprime el banco: 1.234,56, y el negativo con menos adelante."""
    text = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-{text}" if value < 0 else text


@dataclass(frozen=True, slots=True)
class Movement:
    day: str
    """dd/mm/aa, como en el resumen."""
    description: str
    amount: Decimal
    """Negativo, débito; positivo, crédito."""
    reference: str = "0"


def words(text: str, x: float) -> Row:
    """Un texto dividido en palabras, una celda por palabra, desde `x`."""
    cells: Row = []
    for part in text.split(" "):
        cells.append(Cell(part, x))
        x += (len(part) + 1) * CHAR_WIDTH
    return cells


def movement_row(movement: Movement, balance: Decimal) -> Row:
    amount = (
        Cell(money(-movement.amount), DEBIT_RIGHT, right=True)
        if movement.amount < 0
        else Cell(money(movement.amount), CREDIT_RIGHT, right=True)
    )
    return [
        Cell(movement.day, DATE_X),
        *words(movement.description, DESCRIPTION_X),
        Cell(movement.reference, REFERENCE_X),
        amount,
        Cell(money(balance), BALANCE_RIGHT, right=True),
    ]


def table_header() -> Row:
    return [
        Cell("FECHA", 41),
        Cell("DESCRIPCION", 142),
        Cell("REFERENCIA", 264),
        Cell("DEBITOS", 335),
        Cell("CREDITOS", 415),
        Cell("SALDO", 512),
    ]


def balance_row(label: str, balance: Decimal) -> Row:
    return [*words(label, 88), Cell(money(balance), BALANCE_RIGHT, right=True)]


@dataclass(slots=True)
class MacroStatement:
    """Arma el resumen con saldos y totales que cierran; cada prueba rompe lo suyo."""

    opening: Decimal = Decimal("2500.00")
    movements: list[Movement] = field(
        default_factory=lambda: [
            Movement("03/10/26", "COMPRA SUPERMERCADO DEL BARRIO", Decimal("-1500.00"), "123456"),
            Movement("05/10/26", "TRANSF RECIBIDA HABERES", Decimal("250000.00"), "16900"),
            Movement("07/10/26", "N/D DEBITO AUTOMATICO LUZ", Decimal("-12345.67"), "9876543"),
        ]
    )
    currency: str = "PESOS"
    per_page: int = 30
    """Cuántos movimientos entran en una página antes de pasar a la siguiente."""
    totals: tuple[Decimal, Decimal, Decimal, Decimal] | None = None
    """Saldo inicial, créditos, débitos y saldo final del encabezado; si no, los que cierran."""
    after_closing: list[Row] = field(default_factory=list)

    def balances(self) -> list[Decimal]:
        running, result = self.opening, []
        for movement in self.movements:
            running += movement.amount
            result.append(running)
        return result

    def header_totals(self) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        if self.totals is not None:
            return self.totals
        credits = sum((m.amount for m in self.movements if m.amount > 0), Decimal(0))
        debits = sum((-m.amount for m in self.movements if m.amount < 0), Decimal(0))
        return self.opening, credits, debits, self.opening + credits - debits

    def account_rows(self) -> list[Row]:
        initial, credits, debits, final = self.header_totals()
        return [
            words(f"CAJA DE AHORROS EN {self.currency} NRO.: 0-000-0000000000-0", 46),
            [
                *words("SALDO INICIAL", 54),
                Cell("CREDITOS", 172),
                Cell("DEBITOS", 277),
                Cell("I.V.A.", 382),
                *words("SALDO FINAL", 470),
            ],
            [
                Cell(money(initial), 125, right=True),
                Cell(money(credits), 230, right=True),
                Cell(money(debits), 335, right=True),
                Cell(money(Decimal(0)), 436, right=True),
                Cell(money(final), 537, right=True),
            ],
        ]

    def pages(self) -> list[list[Row]]:
        balances = self.balances()
        rows = [movement_row(m, b) for m, b in zip(self.movements, balances, strict=True)]
        chunks = [rows[i : i + self.per_page] for i in range(0, len(rows), self.per_page)] or [[]]
        pages: list[list[Row]] = []
        for index, chunk in enumerate(chunks):
            page = [table_header()]
            if index == 0:
                page = [
                    *self.account_rows(),
                    *page,
                    balance_row("SALDO ULTIMO EXTRACTO AL 30/09/2026", self.opening),
                ]
            else:
                # Algunos resúmenes repiten el saldo que viene de la hoja anterior.
                page.append(balance_row("SALDO ANTERIOR", balances[index * self.per_page - 1]))
            page.extend(chunk)
            if index == len(chunks) - 1:
                last = balances[-1] if balances else self.opening
                page.append(balance_row("SALDO FINAL AL DIA 31/10/2026", last))
                page.extend(self.after_closing)
            page.append(words("Leyenda legal del pie de cada hoja, sin montos.", 20))
            pages.append(page)
        return pages


def to_words(pages: list[list[Row]]) -> list[list[Word]]:
    """Las palabras como las da el adaptador: con caja y altura del renglón."""
    result = []
    for page in pages:
        page_words: list[Word] = []
        for index, row in enumerate(page):
            top = 100.0 + index * ROW_HEIGHT
            page_words.extend(Word(cell.text, cell.x0, cell.x0 + cell.width, top) for cell in row)
        result.append(page_words)
    return result


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def to_pdf(pages: list[list[Row]]) -> bytes:
    """Un PDF mínimo y válido, con Courier, que no necesita incrustar la fuente."""
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # Pages: se completa cuando se conocen las páginas.
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
    ]
    kids = []
    for page in pages:
        commands = []
        for index, row in enumerate(page):
            baseline = PAGE_HEIGHT - 100 - index * ROW_HEIGHT - FONT_SIZE
            for cell in row:
                text = _escape(cell.text)
                commands.append(f"BT /F1 {FONT_SIZE} Tf {cell.x0:.2f} {baseline} Td ({text}) Tj ET")
        stream = "\n".join(commands).encode("latin-1")
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
        content_number = len(objects)
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>"
            % (PAGE_WIDTH, PAGE_HEIGHT, content_number)
        )
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode()
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)
