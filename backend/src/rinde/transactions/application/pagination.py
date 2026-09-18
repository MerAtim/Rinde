"""Cursor de la lista de movimientos.

Se pagina por cursor y no por página numerada: con paginación por número, un
movimiento nuevo corre a todos los demás y la página siguiente repite o saltea
filas. El cursor apunta a una fila concreta, así que eso no pasa.
"""

from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from rinde.transactions.domain.errors import CursorInvalidError

# La lista va de la más reciente a la más vieja, y desempata por identificador
# para que el orden sea total: sin eso, dos movimientos del mismo día podrían
# aparecer en las dos páginas o en ninguna.
_SEPARATOR = "|"


@dataclass(frozen=True, slots=True)
class Cursor:
    occurred_on: date
    transaction_id: UUID

    def encode(self) -> str:
        raw = f"{self.occurred_on.isoformat()}{_SEPARATOR}{self.transaction_id}"
        return urlsafe_b64encode(raw.encode()).decode().rstrip("=")

    @classmethod
    def decode(cls, value: str) -> Cursor:
        """El cursor viene del cliente: se valida como cualquier dato no confiable."""
        try:
            padding = "=" * (-len(value) % 4)
            raw = urlsafe_b64decode(value + padding).decode()
            occurred_on, transaction_id = raw.split(_SEPARATOR)
            return cls(date.fromisoformat(occurred_on), UUID(transaction_id))
        except (ValueError, UnicodeDecodeError) as error:
            raise CursorInvalidError from error
