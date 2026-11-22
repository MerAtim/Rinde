"""Candado de la exportación: cada tabla y cada columna tiene una decisión (ADR-0034).

La lista de tablas sale del esquema, no de una lista escrita a mano. Una tabla o
una columna nueva hace fallar estos tests hasta que se decida, acá y por
escrito, si entra en la exportación y en qué campo, o por qué queda afuera. Así
la exportación no se queda atrás sin que nadie lo note.

Que el campo declarado exista en el registro se comprueba acá. Que la
exportación lo llene con los datos de la base lo prueba el test de integración
contra PostgreSQL.
"""

from dataclasses import fields

import rinde.main  # noqa: F401  (registra todas las tablas en los metadatos)
from rinde.privacy.application import records
from rinde.shared.infrastructure.database import metadata

OWNER = "es la persona misma, que está una sola vez en `profile`"
DERIVED_SEARCH = "la descripción plegada para buscar: sale de `description`"
SAME_KIND = "siempre `expense`: lo repite la base para la clave foránea a la categoría"
MONEY_CURRENCY = "va dentro del monto, como su moneda"

# Tabla -> columna -> "Registro.campo" donde sale en la exportación.
EXPORTED: dict[str, dict[str, str]] = {
    "users": {
        "id": "ProfileRecord.id",
        "username": "ProfileRecord.username",
        "created_at": "ProfileRecord.created_at",
        "demo_expires_at": "ProfileRecord.demo_expires_at",
    },
    "user_preferences": {
        "reference_currency": "PreferencesRecord.reference_currency",
        "rate_type": "PreferencesRecord.rate_type",
        "updated_at": "PreferencesRecord.updated_at",
    },
    "accounts": {
        "id": "AccountRecord.id",
        "name": "AccountRecord.name",
        "kind": "AccountRecord.kind",
        "currency": "AccountRecord.currency",
        "created_at": "AccountRecord.created_at",
        "archived_at": "AccountRecord.archived_at",
    },
    "categories": {
        "id": "CategoryRecord.id",
        "name": "CategoryRecord.name",
        "kind": "CategoryRecord.kind",
        "slug": "CategoryRecord.slug",
        "created_at": "CategoryRecord.created_at",
    },
    "transactions": {
        "id": "TransactionRecord.id",
        "account_id": "TransactionRecord.account_id",
        "kind": "TransactionRecord.kind",
        "amount": "TransactionRecord.money",
        "category_id": "TransactionRecord.category_id",
        "occurred_on": "TransactionRecord.occurred_on",
        "description": "TransactionRecord.description",
        "created_at": "TransactionRecord.created_at",
        "updated_at": "TransactionRecord.updated_at",
        "deleted_at": "TransactionRecord.deleted_at",
        "source_fingerprint": "TransactionRecord.imported",
        "installment_plan_id": "InstallmentRecord.plan_id",
        "installment_number": "InstallmentRecord.number",
        "installment_count": "InstallmentRecord.count",
        "recurring_rule_id": "RecurrenceRecord.rule_id",
        "recurrence_number": "RecurrenceRecord.number",
    },
    "transfers": {
        "id": "TransferRecord.id",
        "from_account_id": "TransferRecord.from_account_id",
        "amount_out": "TransferRecord.sent",
        "to_account_id": "TransferRecord.to_account_id",
        "amount_in": "TransferRecord.received",
        "occurred_on": "TransferRecord.occurred_on",
        "description": "TransferRecord.description",
        "created_at": "TransferRecord.created_at",
        "updated_at": "TransferRecord.updated_at",
        "deleted_at": "TransferRecord.deleted_at",
    },
    "installment_plans": {
        "id": "InstallmentPlanRecord.id",
        "account_id": "InstallmentPlanRecord.account_id",
        "category_id": "InstallmentPlanRecord.category_id",
        "total": "InstallmentPlanRecord.total",
        "count": "InstallmentPlanRecord.count",
        "first_on": "InstallmentPlanRecord.first_on",
        "description": "InstallmentPlanRecord.description",
        "created_at": "InstallmentPlanRecord.created_at",
        "cancelled_at": "InstallmentPlanRecord.cancelled_at",
    },
    "recurring_rules": {
        "id": "RecurringRuleRecord.id",
        "account_id": "RecurringRuleRecord.account_id",
        "kind": "RecurringRuleRecord.kind",
        "category_id": "RecurringRuleRecord.category_id",
        "amount": "RecurringRuleRecord.money",
        "frequency": "RecurringRuleRecord.frequency",
        "starts_on": "RecurringRuleRecord.starts_on",
        "description": "RecurringRuleRecord.description",
        "created_at": "RecurringRuleRecord.created_at",
        "cancelled_at": "RecurringRuleRecord.cancelled_at",
    },
    "transaction_audit": {
        "transaction_id": "HistoryRecord.subject_id",
        "action": "HistoryRecord.action",
        "recorded_at": "HistoryRecord.recorded_at",
        "snapshot": "HistoryRecord.snapshot",
    },
    "transfer_audit": {
        "transfer_id": "HistoryRecord.subject_id",
        "action": "HistoryRecord.action",
        "recorded_at": "HistoryRecord.recorded_at",
        "snapshot": "HistoryRecord.snapshot",
    },
    "budget_limits": {
        "id": "BudgetRecord.id",
        "category_id": "BudgetRecord.category_id",
        "since": "BudgetRecord.since",
        "amount": "BudgetRecord.limit",
        "recorded_at": "BudgetRecord.recorded_at",
    },
    "budget_alerts": {
        "id": "AlertRecord.id",
        "category_id": "AlertRecord.category_id",
        "month": "AlertRecord.month",
        "threshold": "AlertRecord.threshold",
        "limit_amount": "AlertRecord.limit",
        "spent_amount": "AlertRecord.spent",
        "raised_at": "AlertRecord.raised_at",
        "read_at": "AlertRecord.read_at",
    },
    "import_batches": {
        "id": "ImportBatchRecord.id",
        "account_id": "ImportBatchRecord.account_id",
        "file_name": "ImportBatchRecord.file_name",
        "created_at": "ImportBatchRecord.created_at",
        "confirmed_at": "ImportBatchRecord.confirmed_at",
        "imported": "ImportBatchRecord.imported",
        "skipped": "ImportBatchRecord.skipped",
        "errors": "ImportBatchRecord.errors",
    },
    "import_lines": {
        "number": "ImportLineRecord.number",
        "occurred_on": "ImportLineRecord.occurred_on",
        "description": "ImportLineRecord.description",
        "amount": "ImportLineRecord.money",
        "status": "ImportLineRecord.status",
    },
    "category_rules": {
        "id": "CategoryRuleRecord.id",
        "category_id": "CategoryRuleRecord.category_id",
        "kind": "CategoryRuleRecord.kind",
        "pattern": "CategoryRuleRecord.pattern",
        "updated_at": "CategoryRuleRecord.updated_at",
    },
}

# Tabla -> columna -> por qué no sale.
LEFT_OUT: dict[str, dict[str, str]] = {
    "users": {
        "password_hash": "verifica a la persona, no es un dato suyo; exportarlo deja atacarlo "
        "sin conexión a quien robe el archivo",
        "recovery_code_hash": "lo mismo que el hash de la contraseña",
    },
    "user_preferences": {"owner_id": OWNER},
    "accounts": {"owner_id": OWNER},
    "categories": {"owner_id": OWNER},
    "transactions": {
        "owner_id": OWNER,
        "currency": MONEY_CURRENCY,
        "description_search": DERIVED_SEARCH,
    },
    "transfers": {
        "owner_id": OWNER,
        "currency_out": MONEY_CURRENCY,
        "currency_in": MONEY_CURRENCY,
        "description_search": DERIVED_SEARCH,
    },
    "installment_plans": {"owner_id": OWNER, "currency": MONEY_CURRENCY, "kind": SAME_KIND},
    "recurring_rules": {"owner_id": OWNER, "currency": MONEY_CURRENCY},
    "transaction_audit": {
        "id": "identificador interno del registro; el cambio se reconoce por su movimiento y fecha",
        "owner_id": OWNER,
    },
    "transfer_audit": {
        "id": "identificador interno del registro, como en el de movimientos",
        "owner_id": OWNER,
    },
    "budget_limits": {"owner_id": OWNER, "currency": MONEY_CURRENCY, "kind": SAME_KIND},
    "budget_alerts": {"owner_id": OWNER, "currency": MONEY_CURRENCY, "kind": SAME_KIND},
    "import_batches": {
        "owner_id": OWNER,
        "currency": "va dentro del monto de cada línea",
        "file_sha256": "huella del archivo para no importarlo dos veces: sale del archivo, "
        "que la persona ya tiene",
    },
    "import_lines": {
        "batch_id": "cada línea sale dentro de su lote",
        "fingerprint": "huella de la línea para no importarla dos veces: sale de la línea",
    },
    "category_rules": {"owner_id": OWNER},
}

# Tablas que apuntan a `users` pero no salen, y por qué.
TABLES_LEFT_OUT: dict[str, str] = {
    "sessions": "credenciales técnicas de cada sesión abierta (el hash del token y sus "
    "fechas): exportarlas no le dice nada a la persona y ayudaría a un atacante",
    "idempotency_keys": "claves técnicas para no registrar dos veces el mismo pedido; vencen "
    "solas y lo que crearon ya está en su sección",
}

# Tablas que no apuntan a `users`, y por qué no son datos de una persona.
UNLINKED: dict[str, str] = {
    "account_deletions": "constancia de bajas: identificadores de cuentas que ya no existen",
    "client_activity": "topes por origen de red, sin cuenta asociada; se purgan a la hora",
    "failed_login_attempts": "registro de seguridad por nombre de usuario; se borra al "
    "ingresar bien y se purga a los 15 minutos",
    "cpi_months": "índice de precios del INDEC, el mismo para todos",
    "exchange_rates": "cotizaciones públicas, las mismas para todos",
    "alembic_version": "versión del esquema",
}


def _tables_of_a_person() -> set[str]:
    """`users` y todas las que llegan a ella por claves foráneas, directa o indirectamente."""
    reached = {"users"}
    grew = True
    while grew:
        grew = False
        for table in metadata.sorted_tables:
            if table.name not in reached and any(
                key.column.table.name in reached for key in table.foreign_keys
            ):
                reached.add(table.name)
                grew = True
    return reached


def test_toda_tabla_tiene_una_decision() -> None:
    linked = _tables_of_a_person()

    assert linked == set(EXPORTED) | set(TABLES_LEFT_OUT)
    # `alembic_version` no está en los metadatos: la crea Alembic.
    assert {table.name for table in metadata.sorted_tables} - linked == set(UNLINKED) - {
        "alembic_version"
    }


def test_toda_columna_de_una_tabla_exportada_tiene_una_decision() -> None:
    for name, exported in EXPORTED.items():
        columns = {column.name for column in metadata.tables[name].columns}
        left_out = LEFT_OUT.get(name, {})

        assert not set(exported) & set(left_out), name
        assert set(exported) | set(left_out) == columns, name


def test_cada_campo_declarado_existe_en_su_registro() -> None:
    for name, exported in EXPORTED.items():
        for column, target in exported.items():
            record, field = target.split(".")
            assert field in {item.name for item in fields(getattr(records, record))}, (
                f"{name}.{column} -> {target}"
            )
