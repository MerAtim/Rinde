"""Esquema de la exportación: el archivo que se descarga, documentado en OpenAPI.

Copia uno a uno los registros de `privacy.application.records`, que son los que
deciden qué sale. El dinero viaja como string decimal (ADR-0002), con su moneda.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from rinde.privacy.application.records import PersonalData
from rinde.shared.api.schemas import AmountOut
from rinde.shared.domain.money import Currency


class _Record(BaseModel):
    """Se arma leyendo los atributos del registro, sin copiarlos a mano."""

    model_config = ConfigDict(from_attributes=True)


class MoneyOut(_Record):
    amount: AmountOut
    currency: Currency


class ProfileOut(_Record):
    id: UUID
    username: str
    created_at: datetime
    demo_expires_at: datetime | None


class PreferencesOut(_Record):
    reference_currency: str
    rate_type: str
    updated_at: datetime | None = Field(description="Vacío si nunca se cambiaron")


class AccountOut(_Record):
    id: UUID
    name: str
    kind: str
    currency: str
    created_at: datetime
    archived_at: datetime | None


class CategoryOut(_Record):
    id: UUID
    name: str
    kind: str
    slug: str | None = Field(description="Solo en las categorías que sembró Rinde")
    created_at: datetime


class InstallmentOut(_Record):
    plan_id: UUID
    number: int
    count: int


class RecurrenceOut(_Record):
    rule_id: UUID
    number: int


class TransactionOut(_Record):
    id: UUID
    account_id: UUID
    kind: str
    money: MoneyOut
    category_id: UUID
    occurred_on: date
    description: str | None
    imported: bool = Field(description="Si entró por una importación de resumen")
    installment: InstallmentOut | None
    recurrence: RecurrenceOut | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class TransferOut(_Record):
    id: UUID
    from_account_id: UUID
    sent: MoneyOut
    to_account_id: UUID
    received: MoneyOut
    occurred_on: date
    description: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class InstallmentPlanOut(_Record):
    id: UUID
    account_id: UUID
    category_id: UUID
    total: MoneyOut
    count: int
    first_on: date
    description: str | None
    created_at: datetime
    cancelled_at: datetime | None


class RecurringRuleOut(_Record):
    id: UUID
    account_id: UUID
    kind: str
    category_id: UUID
    money: MoneyOut
    frequency: str
    starts_on: date
    description: str | None
    created_at: datetime
    cancelled_at: datetime | None


class HistoryOut(_Record):
    subject_id: UUID = Field(description="El movimiento o la transferencia que cambió")
    action: str
    recorded_at: datetime
    snapshot: dict[str, JsonValue] = Field(description="Cómo quedó después del cambio")


class LedgerOut(_Record):
    categories: list[CategoryOut]
    transactions: list[TransactionOut]
    transfers: list[TransferOut]
    installment_plans: list[InstallmentPlanOut]
    recurring_rules: list[RecurringRuleOut]
    transaction_history: list[HistoryOut]
    transfer_history: list[HistoryOut]


class BudgetOut(_Record):
    id: UUID
    category_id: UUID
    since: date
    limit: MoneyOut | None = Field(description="Vacío: desde ese mes la categoría no tiene tope")
    recorded_at: datetime


class AlertOut(_Record):
    id: UUID
    category_id: UUID
    month: date
    threshold: str
    limit: MoneyOut
    spent: MoneyOut
    raised_at: datetime
    read_at: datetime | None


class ImportErrorOut(_Record):
    line: int
    problem: str


class ImportLineOut(_Record):
    number: int
    occurred_on: date
    description: str | None
    money: MoneyOut = Field(description="Con signo, como en el archivo: negativo es un gasto")
    status: str


class ImportBatchOut(_Record):
    id: UUID
    account_id: UUID
    file_name: str
    created_at: datetime
    confirmed_at: datetime | None
    imported: int
    skipped: int
    errors: list[ImportErrorOut]
    lines: list[ImportLineOut]


class CategoryRuleOut(_Record):
    id: UUID
    pattern: str
    category_id: UUID
    kind: str
    updated_at: datetime


class ImportsOut(_Record):
    batches: list[ImportBatchOut]
    category_rules: list[CategoryRuleOut]


class PersonalDataResponse(_Record):
    format_version: int = Field(description="Sube si cambia algo que un lector no esperaría")
    generated_at: datetime
    profile: ProfileOut
    preferences: PreferencesOut
    accounts: list[AccountOut]
    ledger: LedgerOut
    budgets: list[BudgetOut]
    alerts: list[AlertOut]
    imports: ImportsOut

    @classmethod
    def from_data(cls, data: PersonalData) -> PersonalDataResponse:
        return cls.model_validate(data)
