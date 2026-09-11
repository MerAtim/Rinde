"""Exporta el contrato OpenAPI de la API a un archivo JSON.

Uso: python -m rinde.openapi <ruta de salida>

El archivo se versiona: el frontend genera sus tipos a partir de él y la CI
verifica que coincida con el código.
"""

import json
import sys
from contextlib import AbstractAsyncContextManager
from pathlib import Path

from pydantic import SecretStr

from rinde.auth.application.unit import AuthUnit
from rinde.config import Settings
from rinde.main import create_app


class _UnusedDatabaseProbe:
    """Exportar el contrato no consulta la base de datos."""

    async def is_reachable(self) -> bool:  # pragma: no cover
        msg = "La base de datos no se consulta al exportar el contrato"
        raise AssertionError(msg)


class _UnusedAuthFactory:
    """Exportar el contrato no abre sesiones ni conexiones."""

    def __call__(self) -> AbstractAsyncContextManager[AuthUnit]:  # pragma: no cover
        msg = "La autenticación no se usa al exportar el contrato"
        raise AssertionError(msg)


def export(path: Path) -> None:
    settings = Settings(
        environment="development",
        database_url=SecretStr("postgresql+psycopg://openapi@localhost/openapi"),
    )
    app = create_app(
        settings, database_probe=_UnusedDatabaseProbe(), auth_factory=_UnusedAuthFactory()
    )
    contract = json.dumps(app.openapi(), indent=2, ensure_ascii=False)
    # Siempre LF, también en Windows: el archivo se compara byte a byte en CI.
    path.write_text(f"{contract}\n", encoding="utf-8", newline="\n")


def main() -> None:
    if len(sys.argv) != 2:  # noqa: PLR2004
        sys.exit("Uso: python -m rinde.openapi <ruta de salida>")
    export(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
