"""El formato de la exportación: todo lo que Rinde guarda de una persona (ADR-0034).

Son registros propios de este módulo, no las entidades de los otros: así el
formato no cambia solo porque cambie el dominio de un módulo, y lo que entra en
el archivo se elige campo por campo. Quedan afuera, a propósito:

* Los hashes de la contraseña y del código de recuperación: no son datos de la
  persona sino la forma de verificarla.
* Los valores derivados que la base guarda para buscar o para no importar dos
  veces lo mismo (la descripción plegada, las huellas SHA-256 de cada línea y de
  cada archivo): se calculan de lo que sí se exporta.
* El dueño de cada fila: es siempre la persona, que está en `profile`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from rinde.shared.domain.money import Money

FORMAT_VERSION = 1
"""Sube cuando cambia algo que un programa que ya lee el archivo no esperaría."""


@dataclass(frozen=True, slots=True)
class ProfileRecord:
    id: UUID
    username: str
    created_at: datetime
    demo_expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class PreferencesRecord:
    reference_currency: str
    rate_type: str
    updated_at: datetime | None
    """`None` si nunca se cambiaron: valen las de por defecto."""


@dataclass(frozen=True, slots=True)
class AccountRecord:
    id: UUID
    name: str
    kind: str
    currency: str
    created_at: datetime
    archived_at: datetime | None


@dataclass(frozen=True, slots=True)
class CategoryRecord:
    id: UUID
    name: str
    kind: str
    slug: str | None
    """Solo en las categorías que Rinde sembró: con qué clave se traduce su nombre."""
    created_at: datetime


@dataclass(frozen=True, slots=True)
class InstallmentRecord:
    plan_id: UUID
    number: int
    count: int


@dataclass(frozen=True, slots=True)
class RecurrenceRecord:
    rule_id: UUID
    number: int


@dataclass(frozen=True, slots=True)
class TransactionRecord:
    id: UUID
    account_id: UUID
    kind: str
    money: Money
    category_id: UUID
    occurred_on: date
    description: str | None
    imported: bool
    installment: InstallmentRecord | None
    recurrence: RecurrenceRecord | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class TransferRecord:
    id: UUID
    from_account_id: UUID
    sent: Money
    to_account_id: UUID
    received: Money
    occurred_on: date
    description: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class InstallmentPlanRecord:
    id: UUID
    account_id: UUID
    category_id: UUID
    total: Money
    count: int
    first_on: date
    description: str | None
    created_at: datetime
    cancelled_at: datetime | None


@dataclass(frozen=True, slots=True)
class RecurringRuleRecord:
    id: UUID
    account_id: UUID
    kind: str
    category_id: UUID
    money: Money
    frequency: str
    starts_on: date
    description: str | None
    created_at: datetime
    cancelled_at: datetime | None


@dataclass(frozen=True, slots=True)
class HistoryRecord:
    """Un cambio del log de auditoría: qué pasó, cuándo y cómo quedó."""

    subject_id: UUID
    action: str
    recorded_at: datetime
    snapshot: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class LedgerRecords:
    categories: list[CategoryRecord]
    transactions: list[TransactionRecord]
    transfers: list[TransferRecord]
    installment_plans: list[InstallmentPlanRecord]
    recurring_rules: list[RecurringRuleRecord]
    transaction_history: list[HistoryRecord]
    transfer_history: list[HistoryRecord]


@dataclass(frozen=True, slots=True)
class BudgetRecord:
    """Una vigencia de un tope: desde `since`; sin `limit`, la categoría dejó de tenerlo."""

    id: UUID
    category_id: UUID
    since: date
    limit: Money | None
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class AlertRecord:
    id: UUID
    category_id: UUID
    month: date
    threshold: str
    limit: Money
    spent: Money
    raised_at: datetime
    read_at: datetime | None


@dataclass(frozen=True, slots=True)
class ImportErrorRecord:
    line: int
    problem: str


@dataclass(frozen=True, slots=True)
class ImportLineRecord:
    number: int
    occurred_on: date
    description: str | None
    money: Money
    """Con signo, como venía en el archivo: negativo es un gasto."""
    status: str


@dataclass(frozen=True, slots=True)
class ImportBatchRecord:
    id: UUID
    account_id: UUID
    file_name: str
    created_at: datetime
    confirmed_at: datetime | None
    imported: int
    skipped: int
    errors: list[ImportErrorRecord]
    lines: list[ImportLineRecord]


@dataclass(frozen=True, slots=True)
class CategoryRuleRecord:
    """Lo que la importación aprendió: una descripción así va a esta categoría."""

    id: UUID
    pattern: str
    category_id: UUID
    kind: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ImportRecords:
    batches: list[ImportBatchRecord]
    category_rules: list[CategoryRuleRecord]


@dataclass(frozen=True, slots=True)
class PersonalData:
    format_version: int
    generated_at: datetime
    profile: ProfileRecord
    preferences: PreferencesRecord
    accounts: list[AccountRecord]
    ledger: LedgerRecords
    budgets: list[BudgetRecord]
    alerts: list[AlertRecord]
    imports: ImportRecords
