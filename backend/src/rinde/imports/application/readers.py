"""Los lectores que necesitan algo de afuera para leer su formato (ADR-0023)."""

from rinde.imports.application.ports import PdfText
from rinde.imports.domain.errors import ImportFileTooLargeError
from rinde.imports.domain.macro_pdf import MAX_PAGES, read_macro
from rinde.imports.domain.statement import MAX_BYTES, Statement


class MacroPdfReader:
    """El resumen PDF de Banco Macro: el adaptador saca las palabras y el dominio las lee."""

    def __init__(self, pdf: PdfText) -> None:
        self._pdf = pdf

    def read(self, content: bytes) -> Statement:
        if len(content) > MAX_BYTES:
            raise ImportFileTooLargeError
        return read_macro(self._pdf.pages(content, MAX_PAGES))
