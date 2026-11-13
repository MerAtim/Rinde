"""La capa de texto de un PDF con pdfplumber (ADR-0023).

El archivo lo sube la persona: es un input no confiable, y un PDF es un formato
complejo. Por eso se mira la firma antes de abrirlo, se cuentan las páginas
antes de leer ninguna y solo se extrae texto, sin dibujar la página. El tamaño
ya llega acotado (1 MB) por el borde y por el caso de uso.
"""

from io import BytesIO

import pdfplumber

from rinde.imports.domain.errors import (
    ImportPdfInvalidError,
    ImportPdfTooManyPagesError,
    StatementImportError,
)
from rinde.imports.domain.macro_pdf import Word

SIGNATURE = b"%PDF-"
SIGNATURE_WINDOW = 1024
"""La norma admite bytes antes de la firma, dentro del primer kilobyte (ISO 32000-1, 7.5.2)."""


class PdfPlumberText:
    def pages(self, content: bytes, max_pages: int) -> list[list[Word]]:
        if SIGNATURE not in content[:SIGNATURE_WINDOW]:
            raise ImportPdfInvalidError
        try:
            with pdfplumber.open(BytesIO(content)) as pdf:
                if len(pdf.pages) > max_pages:
                    raise ImportPdfTooManyPagesError
                return [
                    [
                        Word(
                            str(word["text"]),
                            float(word["x0"]),
                            float(word["x1"]),
                            float(word["top"]),
                        )
                        for word in page.extract_words()
                    ]
                    for page in pdf.pages
                ]
        except StatementImportError:
            raise
        # Un PDF dañado, cifrado o malicioso puede fallar de muchas formas dentro
        # de pdfminer, sin una excepción base común: cualquiera es un PDF inválido.
        except Exception as error:
            raise ImportPdfInvalidError from error
