"""La lectura del PDF en un proceso aparte: lo que lee, lo que corta y lo que mata."""

import os
import sys
import time
import zlib

import pytest

from rinde.imports.domain.errors import ImportPdfInvalidError, ImportPdfTooManyPagesError
from rinde.imports.domain.macro_pdf import MAX_PAGES, Word
from rinde.imports.infrastructure.pdf import PdfPlumberText
from rinde.imports.infrastructure.sandbox import SandboxedPdfText
from tests.unit.imports.macro_statement import MacroStatement, to_pdf


def _sleeps(content: bytes, max_pages: int) -> list[list[Word]]:
    time.sleep(60)
    return []


def _dies(content: bytes, max_pages: int) -> list[list[Word]]:
    os._exit(1)


def _bomb(decoded_bytes: int) -> bytes:
    """Un PDF de una página cuyo contenido comprimido se infla a `decoded_bytes`."""
    stream = zlib.compress(b" " * decoded_bytes, 9)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>",
        b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return out


def test_reads_the_same_as_without_the_sandbox() -> None:
    content = to_pdf(MacroStatement(per_page=2).pages())

    assert SandboxedPdfText().pages(content, MAX_PAGES) == PdfPlumberText().pages(
        content, MAX_PAGES
    )


def test_a_domain_error_crosses_the_process_as_it_is() -> None:
    pages = MacroStatement(per_page=1).pages()

    with pytest.raises(ImportPdfTooManyPagesError):
        SandboxedPdfText().pages(to_pdf([pages[0]] * (MAX_PAGES + 1)), MAX_PAGES)


def test_something_that_is_not_a_pdf_is_invalid() -> None:
    with pytest.raises(ImportPdfInvalidError):
        SandboxedPdfText().pages(b"%PDF-1.4\n esto no es un PDF", MAX_PAGES)


def test_a_reading_that_does_not_end_is_killed() -> None:
    started = time.monotonic()

    with pytest.raises(ImportPdfInvalidError):
        SandboxedPdfText(_sleeps, wall_seconds=1).pages(b"%PDF-", MAX_PAGES)

    assert time.monotonic() - started < 20


def test_a_process_that_dies_without_answering_is_invalid() -> None:
    with pytest.raises(ImportPdfInvalidError):
        SandboxedPdfText(_dies).pages(b"%PDF-", MAX_PAGES)


@pytest.mark.skipif(sys.platform != "linux", reason="el tope de memoria es de Linux")
def test_a_decompression_bomb_hits_the_memory_cap() -> None:
    # 200 kB que se inflan a 256 MB: sin tope, la lectura pasa de 400 MB.
    bomb = _bomb(256 * 1024 * 1024)
    assert len(bomb) < 300 * 1024

    with pytest.raises(ImportPdfInvalidError):
        SandboxedPdfText(memory_budget=64 * 1024 * 1024).pages(bomb, MAX_PAGES)
