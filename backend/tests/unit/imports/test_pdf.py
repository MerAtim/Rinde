"""La capa de texto con pdfplumber, sobre PDF de verdad armados en el test."""

import pytest

from rinde.imports.application.readers import MacroPdfReader
from rinde.imports.domain.errors import (
    ImportFileTooLargeError,
    ImportPdfInvalidError,
    ImportPdfTooManyPagesError,
)
from rinde.imports.domain.macro_pdf import MAX_PAGES, read_macro
from rinde.imports.domain.statement import MAX_BYTES
from rinde.imports.infrastructure.pdf import PdfPlumberText
from tests.unit.imports.macro_statement import MacroStatement, to_pdf, to_words


def test_the_pdf_reads_the_same_as_its_words() -> None:
    source = MacroStatement(per_page=2)

    from_pdf = MacroPdfReader(PdfPlumberText()).read(to_pdf(source.pages()))

    assert from_pdf == read_macro(to_words(source.pages()))
    assert len(from_pdf.lines) == len(source.movements)


@pytest.mark.parametrize(
    "content",
    [
        b"Fecha;Descripcion;Importe\n03/10/2026;CAFE;-900,00\n",
        b"",
        b"%PDF-1.4\n esto no es un PDF",
        to_pdf(MacroStatement().pages())[:200],
    ],
    ids=["un CSV", "vacio", "firma sin PDF", "cortado"],
)
def test_something_that_is_not_a_readable_pdf(content: bytes) -> None:
    with pytest.raises(ImportPdfInvalidError):
        PdfPlumberText().pages(content, MAX_PAGES)


def test_more_pages_than_a_statement_has() -> None:
    pages = MacroStatement(per_page=1).pages()
    content = to_pdf([pages[0]] * (MAX_PAGES + 1))

    with pytest.raises(ImportPdfTooManyPagesError):
        PdfPlumberText().pages(content, MAX_PAGES)


def test_a_file_over_the_limit_is_not_opened() -> None:
    with pytest.raises(ImportFileTooLargeError):
        MacroPdfReader(PdfPlumberText()).read(b"%PDF-" + b"0" * MAX_BYTES)
