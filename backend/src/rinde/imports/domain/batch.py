"""El lote: un archivo leído, esperando que la persona lo confirme (ADR-0023).

Reglas:

* **Cada línea tiene una huella**, SHA-256 de cuenta, fecha, monto, descripción
  y cuántas veces apareció antes esa misma combinación en el archivo. Dos cafés
  iguales del mismo día son dos líneas; reimportar el archivo da las mismas.
* **Duplicado:** su huella ya entró en la cuenta. Nunca se importa.
* **Posible duplicado:** la cuenta ya tiene un movimiento con la misma fecha y el
  mismo monto, por ejemplo cargado a mano. Queda afuera salvo que la persona lo
  incluya. Cada movimiento existente cubre a una sola línea: si había un café
  cargado y el archivo trae dos, el segundo es nuevo.
* **El lote vence** a las 24 horas si nadie lo confirma.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from rinde.imports.domain.statement import LineError, LineProblem, ParsedLine, Statement
from rinde.shared.domain.money import Currency
from rinde.shared.domain.text import fold

BATCH_TTL = timedelta(hours=24)

FUTURE_TOLERANCE = timedelta(days=1)
"""La misma de un movimiento cargado a mano: la zona horaria de quien carga."""


class LineStatus(StrEnum):
    NEW = "new"
    DUPLICATE = "duplicate"
    POSSIBLE_DUPLICATE = "possible_duplicate"


@dataclass(frozen=True, slots=True)
class BatchLine:
    number: int
    occurred_on: date
    description: str | None
    signed_amount: Decimal
    fingerprint: str
    status: LineStatus


@dataclass(frozen=True, slots=True)
class ExistingMovement:
    occurred_on: date
    signed_amount: Decimal


@dataclass(frozen=True, slots=True)
class AccountState:
    """Lo que la cuenta ya tiene, en el período del archivo."""

    currency: Currency
    imported: set[str]
    """Huellas que ya entraron."""
    existing: list[ExistingMovement]


@dataclass(frozen=True, slots=True)
class ImportBatch:
    id: UUID
    owner_id: UUID
    account_id: UUID
    currency: Currency
    file_name: str
    file_sha256: str
    created_at: datetime
    lines: list[BatchLine]
    errors: list[LineError]
    confirmed_at: datetime | None = None
    imported: int = 0
    skipped: int = 0

    @property
    def expires_at(self) -> datetime:
        return self.created_at + BATCH_TTL

    def is_expired(self, now: datetime) -> bool:
        return self.confirmed_at is None and now >= self.expires_at


_SEPARATOR = "\x1f"


def fingerprints(account_id: UUID, lines: list[ParsedLine]) -> list[str]:
    """Una huella por línea, en el mismo orden."""
    seen: Counter[tuple[date, Decimal, str]] = Counter()
    result = []
    for line in lines:
        # Plegada y sin espacios de más: "COTO  Nro 12" y "Coto Nro 12" son lo mismo.
        text = " ".join(fold(line.description or "").split())
        amount = line.signed_amount.normalize()
        key = (line.occurred_on, amount, text)
        occurrence = seen[key]
        seen[key] += 1
        raw = _SEPARATOR.join(
            [
                str(account_id),
                line.occurred_on.isoformat(),
                format(amount, "f"),
                text,
                str(occurrence),
            ]
        )
        result.append(sha256(raw.encode()).hexdigest())
    return result


@dataclass(frozen=True, slots=True)
class Classified:
    lines: list[BatchLine]
    errors: list[LineError]


def classify(
    statement: Statement, hashes: list[str], account: AccountState, today: date
) -> Classified:
    """Marca cada línea, y pasa a error lo que la cuenta no puede aceptar.

    Lo que el lector no sabía: la precisión de la moneda de la cuenta y qué día
    es hoy.
    """
    currency, imported = account.currency, account.imported
    available = Counter((item.occurred_on, item.signed_amount) for item in account.existing)
    # Primero, lo que ya entró por huella: su movimiento existente es el suyo, y
    # no puede marcar como posible duplicado a otra línea.
    for line, fingerprint in zip(statement.lines, hashes, strict=True):
        key = (line.occurred_on, line.signed_amount)
        if fingerprint in imported and available[key] > 0:
            available[key] -= 1
    lines: list[BatchLine] = []
    errors = list(statement.errors)
    latest = today + FUTURE_TOLERANCE
    for line, fingerprint in zip(statement.lines, hashes, strict=True):
        if line.signed_amount != line.signed_amount.quantize(currency.quantum):
            errors.append(LineError(line.number, LineProblem.AMOUNT_TOO_PRECISE))
            continue
        if line.occurred_on > latest:
            errors.append(LineError(line.number, LineProblem.DATE_IN_FUTURE))
            continue
        key = (line.occurred_on, line.signed_amount)
        if fingerprint in imported:
            status = LineStatus.DUPLICATE
        elif available[key] > 0:
            available[key] -= 1
            status = LineStatus.POSSIBLE_DUPLICATE
        else:
            status = LineStatus.NEW
        lines.append(
            BatchLine(
                number=line.number,
                occurred_on=line.occurred_on,
                description=line.description,
                signed_amount=line.signed_amount,
                fingerprint=fingerprint,
                status=status,
            )
        )
    errors.sort(key=lambda error: error.number)
    return Classified(lines, errors)
