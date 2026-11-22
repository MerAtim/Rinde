"""Adaptadores hacia los otros módulos: privacidad los lee por su capa de aplicación.

Cada adaptador abre su propia unidad de trabajo, con su sesión, y la cierra al
terminar. Son solo lecturas. Acá se elige, campo por campo, qué entra en la
exportación: lo que no se copia a un registro no sale (ver `records`).
"""

from uuid import UUID

from rinde.accounts.application.unit import AccountsUnitFactory
from rinde.alerts.application.unit import AlertsUnitFactory
from rinde.auth.application.unit import AuthUnitFactory
from rinde.budgets.application.unit import BudgetsUnitFactory
from rinde.imports.application.unit import ImportsUnitFactory
from rinde.preferences.application.unit import PreferencesUnitFactory
from rinde.privacy.application.records import (
    AccountRecord,
    AlertRecord,
    BudgetRecord,
    CategoryRecord,
    CategoryRuleRecord,
    HistoryRecord,
    ImportBatchRecord,
    ImportErrorRecord,
    ImportLineRecord,
    ImportRecords,
    InstallmentPlanRecord,
    InstallmentRecord,
    LedgerRecords,
    PreferencesRecord,
    ProfileRecord,
    RecurrenceRecord,
    RecurringRuleRecord,
    TransactionRecord,
    TransferRecord,
)
from rinde.shared.domain.money import Money
from rinde.transactions.application.ports import AuditEntry
from rinde.transactions.application.unit import TransactionsUnitFactory


class AuthProfileReader:
    def __init__(self, factory: AuthUnitFactory) -> None:
        self._factory = factory

    async def profile(self, owner_id: UUID) -> ProfileRecord:
        async with self._factory() as unit:
            profile = await unit.profile.execute(owner_id)
        return ProfileRecord(
            id=profile.id,
            username=profile.username,
            created_at=profile.created_at,
            demo_expires_at=profile.demo_expires_at,
        )


class ModulePreferencesReader:
    def __init__(self, factory: PreferencesUnitFactory) -> None:
        self._factory = factory

    async def preferences(self, owner_id: UUID) -> PreferencesRecord:
        async with self._factory() as unit:
            preferences = await unit.get.execute(owner_id)
        return PreferencesRecord(
            reference_currency=preferences.reference_currency.value,
            rate_type=preferences.rate_type.value,
            updated_at=preferences.updated_at,
        )


class ModuleAccountsReader:
    def __init__(self, factory: AccountsUnitFactory) -> None:
        self._factory = factory

    async def accounts(self, owner_id: UUID) -> list[AccountRecord]:
        async with self._factory() as unit:
            accounts = await unit.list.execute(owner_id, include_archived=True)
        return [
            AccountRecord(
                id=account.id,
                name=account.name.value,
                kind=account.kind.value,
                currency=account.currency.value,
                created_at=account.created_at,
                archived_at=account.archived_at,
            )
            for account in accounts
        ]


def _history(entries: list[AuditEntry]) -> list[HistoryRecord]:
    return [
        HistoryRecord(
            subject_id=entry.subject_id,
            action=entry.action.value,
            recorded_at=entry.recorded_at,
            snapshot=entry.snapshot,
        )
        for entry in entries
    ]


class TransactionsLedgerReader:
    def __init__(self, factory: TransactionsUnitFactory) -> None:
        self._factory = factory

    async def ledger(self, owner_id: UUID) -> LedgerRecords:
        async with self._factory() as unit:
            ledger = await unit.export.execute(owner_id)
        return LedgerRecords(
            categories=[
                CategoryRecord(
                    id=category.id,
                    name=category.name.value,
                    kind=category.kind.value,
                    slug=category.slug,
                    created_at=category.created_at,
                )
                for category in ledger.categories
            ],
            transactions=[
                TransactionRecord(
                    id=item.id,
                    account_id=item.account_id,
                    kind=item.kind.value,
                    money=item.money,
                    category_id=item.category_id,
                    occurred_on=item.occurred_on,
                    description=item.description.value if item.description else None,
                    imported=item.source_fingerprint is not None,
                    installment=None
                    if item.installment is None
                    else InstallmentRecord(
                        plan_id=item.installment.plan_id,
                        number=item.installment.number,
                        count=item.installment.count,
                    ),
                    recurrence=None
                    if item.recurrence is None
                    else RecurrenceRecord(
                        rule_id=item.recurrence.rule_id, number=item.recurrence.number
                    ),
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    deleted_at=item.deleted_at,
                )
                for item in ledger.transactions
            ],
            transfers=[
                TransferRecord(
                    id=transfer.id,
                    from_account_id=transfer.from_account_id,
                    sent=transfer.sent,
                    to_account_id=transfer.to_account_id,
                    received=transfer.received,
                    occurred_on=transfer.occurred_on,
                    description=transfer.description.value if transfer.description else None,
                    created_at=transfer.created_at,
                    updated_at=transfer.updated_at,
                    deleted_at=transfer.deleted_at,
                )
                for transfer in ledger.transfers
            ],
            installment_plans=[
                InstallmentPlanRecord(
                    id=plan.id,
                    account_id=plan.account_id,
                    category_id=plan.category_id,
                    total=plan.total,
                    count=plan.count,
                    first_on=plan.first_on,
                    description=plan.description.value if plan.description else None,
                    created_at=plan.created_at,
                    cancelled_at=plan.cancelled_at,
                )
                for plan in ledger.installment_plans
            ],
            recurring_rules=[
                RecurringRuleRecord(
                    id=rule.id,
                    account_id=rule.account_id,
                    kind=rule.kind.value,
                    category_id=rule.category_id,
                    money=rule.money,
                    frequency=rule.frequency.value,
                    starts_on=rule.starts_on,
                    description=rule.description.value if rule.description else None,
                    created_at=rule.created_at,
                    cancelled_at=rule.cancelled_at,
                )
                for rule in ledger.recurring_rules
            ],
            transaction_history=_history(ledger.transaction_history),
            transfer_history=_history(ledger.transfer_history),
        )


class ModuleBudgetsReader:
    def __init__(self, factory: BudgetsUnitFactory) -> None:
        self._factory = factory

    async def budgets(self, owner_id: UUID) -> list[BudgetRecord]:
        async with self._factory() as unit:
            limits = await unit.export.execute(owner_id)
        return [
            BudgetRecord(
                id=limit.id,
                category_id=limit.category_id,
                since=limit.since,
                limit=limit.limit,
                recorded_at=limit.recorded_at,
            )
            for limit in limits
        ]


class ModuleAlertsReader:
    def __init__(self, factory: AlertsUnitFactory) -> None:
        self._factory = factory

    async def alerts(self, owner_id: UUID) -> list[AlertRecord]:
        async with self._factory() as unit:
            alerts = await unit.export.execute(owner_id)
        return [
            AlertRecord(
                id=alert.id,
                category_id=alert.category_id,
                month=alert.month,
                threshold=alert.threshold.value,
                limit=alert.limit,
                spent=alert.spent,
                raised_at=alert.raised_at,
                read_at=alert.read_at,
            )
            for alert in alerts
        ]


class ModuleImportsReader:
    def __init__(self, factory: ImportsUnitFactory) -> None:
        self._factory = factory

    async def imports(self, owner_id: UUID) -> ImportRecords:
        async with self._factory() as unit:
            exported = await unit.export.execute(owner_id)
        return ImportRecords(
            batches=[
                ImportBatchRecord(
                    id=batch.id,
                    account_id=batch.account_id,
                    file_name=batch.file_name,
                    created_at=batch.created_at,
                    confirmed_at=batch.confirmed_at,
                    imported=batch.imported,
                    skipped=batch.skipped,
                    errors=[
                        ImportErrorRecord(line=error.number, problem=error.problem.value)
                        for error in batch.errors
                    ],
                    lines=[
                        ImportLineRecord(
                            number=line.number,
                            occurred_on=line.occurred_on,
                            description=line.description,
                            money=Money(line.signed_amount, batch.currency),
                            status=line.status.value,
                        )
                        for line in batch.lines
                    ],
                )
                for batch in exported.batches
            ],
            category_rules=[
                CategoryRuleRecord(
                    id=rule.id,
                    pattern=rule.pattern,
                    category_id=rule.category_id,
                    kind="expense" if rule.is_expense else "income",
                    updated_at=rule.updated_at,
                )
                for rule in exported.rules
            ],
        )
