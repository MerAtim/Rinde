"""La lectura del PDF, en un proceso aparte con tope de memoria, CPU y tiempo.

Un PDF guarda su contenido comprimido, y un archivo chico puede inflarse mil
veces al leerlo (una bomba de descompresión): 200 kB llegaron a 374 MB de
memoria en una medición, y el límite de 1 MB deja pasar uno que tumba una
instancia de 512 MB. pdfminer no tiene un tope propio, así que el tope lo pone
el sistema operativo sobre un proceso descartable (OWASP, "File Upload Cheat
Sheet"; CWE-409). Si el archivo se pasa, muere ese proceso y la API responde
que el PDF no se pudo leer; el servidor sigue en pie.

Los topes de memoria y de CPU son de Linux, donde corren producción y la CI.
En Windows el proceso aparte y el tope de tiempo funcionan igual, sin los otros
dos: es solo el entorno de desarrollo.
"""

import multiprocessing
import os
import sys
import threading
from collections.abc import Callable
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Final

from rinde.imports.domain.errors import ImportPdfInvalidError, StatementImportError
from rinde.imports.domain.macro_pdf import Word
from rinde.imports.infrastructure.pdf import PdfPlumberText

type Extract = Callable[[bytes, int], list[list[Word]]]

MEMORY_BUDGET: Final = 192 * 1024 * 1024
"""Memoria que puede sumar la lectura sobre lo que el proceso ya ocupa.

Un resumen real se lee con pocos megas. Con este margen, la API, el proceso
aparte y su tope entran juntos en los 512 MB de la instancia de producción.
"""
CPU_SECONDS: Final = 20
WALL_SECONDS: Final = 30
"""El tiempo de reloj cubre lo que el de CPU no ve: un proceso que espera sin calcular."""


def plumber_pages(content: bytes, max_pages: int) -> list[list[Word]]:
    return PdfPlumberText().pages(content, max_pages)


def _limit_resources(memory_budget: int, cpu_seconds: int) -> None:
    if sys.platform != "linux":
        return
    import resource  # noqa: PLC0415  (solo existe en sistemas POSIX)

    pages_in_use = int(Path("/proc/self/statm").read_text(encoding="ascii").split()[0])
    current = pages_in_use * os.sysconf("SC_PAGE_SIZE")
    # Se mide después de importar pdfplumber: el tope cuenta solo lo que suma la lectura.
    memory = current + memory_budget
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))


def _child(  # noqa: PLR0913  (todo viaja por argumento: el proceso no comparte nada)
    *,
    extract: Extract,
    content: bytes,
    max_pages: int,
    memory_budget: int,
    cpu_seconds: int,
    result: Connection,
) -> None:
    try:
        _limit_resources(memory_budget, cpu_seconds)
        result.send(("ok", extract(content, max_pages)))
    except StatementImportError as error:
        result.send(("domain", error))
    # Sin memoria, cualquier cosa puede fallar, también avisarlo: si el aviso no
    # llega, el padre ve el caño cerrado y lo trata igual.
    except BaseException:
        result.send(("invalid", None))
    finally:
        result.close()


class SandboxedPdfText:
    """Mismo puerto que `PdfPlumberText`, con la lectura en un proceso descartable."""

    def __init__(
        self,
        extract: Extract = plumber_pages,
        *,
        memory_budget: int = MEMORY_BUDGET,
        cpu_seconds: int = CPU_SECONDS,
        wall_seconds: float = WALL_SECONDS,
    ) -> None:
        self._extract = extract
        self._memory_budget = memory_budget
        self._cpu_seconds = cpu_seconds
        self._wall_seconds = wall_seconds
        # De a una lectura por vez: varias juntas sumarían sus topes de memoria.
        self._one_at_a_time = threading.Lock()

    def pages(self, content: bytes, max_pages: int) -> list[list[Word]]:
        with self._one_at_a_time:
            kind, value = self._run(content, max_pages)
        if kind == "ok" and isinstance(value, list):
            return value
        if kind == "domain" and isinstance(value, StatementImportError):
            raise value
        raise ImportPdfInvalidError

    def _run(self, content: bytes, max_pages: int) -> tuple[str, object]:
        # spawn y no fork: el proceso nuevo no hereda la memoria ni las conexiones de la API.
        context = multiprocessing.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(
            target=_child,
            kwargs={
                "extract": self._extract,
                "content": content,
                "max_pages": max_pages,
                "memory_budget": self._memory_budget,
                "cpu_seconds": self._cpu_seconds,
                "result": sender,
            },
            daemon=True,
        )
        process.start()
        sender.close()
        try:
            if not receiver.poll(self._wall_seconds):
                return ("invalid", None)
            message: tuple[str, object] = receiver.recv()
        except EOFError:
            # El proceso murió sin avisar: lo mató el tope de CPU o se cayó.
            return ("invalid", None)
        finally:
            receiver.close()
            process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join()
        return message
