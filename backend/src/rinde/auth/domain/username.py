"""Nombre de usuario: el único identificador de una cuenta (ADR-0007)."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Self

from rinde.auth.domain.errors import UsernameInvalidError, UsernameReservedError

MIN_LENGTH = 3
MAX_LENGTH = 30
# Las cuentas demo se llaman así (ADR-0028): nadie más puede registrarse con este prefijo.
DEMO_PREFIX = "demo-"
_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?")
_RESERVED = frozenset(
    {
        "admin",
        "administrador",
        "api",
        "null",
        "rinde",
        "root",
        "sistema",
        "soporte",
        "support",
        "system",
        "undefined",
    }
)


@dataclass(frozen=True, slots=True)
class Username:
    """Normalizado: minúsculas ASCII, dígitos, punto, guion y guion bajo."""

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        value = unicodedata.normalize("NFKC", raw).strip().casefold()
        if not MIN_LENGTH <= len(value) <= MAX_LENGTH or not _PATTERN.fullmatch(value):
            raise UsernameInvalidError
        if value in _RESERVED:
            raise UsernameReservedError
        return cls(value)

    @property
    def is_demo(self) -> bool:
        return self.value.startswith(DEMO_PREFIX)
