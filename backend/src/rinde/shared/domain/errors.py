"""Error base del dominio. Cada error lleva un código estable que la API devuelve tal cual."""

from typing import ClassVar


class DomainError(Exception):
    code: ClassVar[str] = "DOMAIN_ERROR"
