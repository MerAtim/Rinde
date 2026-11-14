"""Tablas de movimientos, categorías, auditoría e idempotencia (SQLAlchemy Core).

Las reglas del dominio se repiten como restricciones de la base: si algún día
alguien escribe una fila sin pasar por el dominio, la base la rechaza igual.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    SmallInteger,
    String,
    Table,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from rinde.shared.infrastructure.database import metadata

_KINDS = "('income', 'expense')"

categories = Table(
    "categories",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(40), nullable=False),
    Column("kind", String(8), nullable=False),
    # Solo en las sembradas: la interfaz las traduce por este identificador (ADR-0011).
    Column("slug", String(40), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 40", name="name_length"),
    CheckConstraint(f"kind IN {_KINDS}", name="kind_known"),
    # El movimiento apunta a (id, dueño, tipo): así la base garantiza que una
    # categoría de gastos no clasifique un ingreso, y que sea de la misma persona.
    Index("uq_categories_id_owner_id_kind", "id", "owner_id", "kind", unique=True),
    # "Súper" y "súper" son la misma categoría dentro de un tipo.
    Index(
        "uq_categories_owner_id_kind_name",
        "owner_id",
        "kind",
        func.lower(text("name")),
        unique=True,
    ),
    # Una sola categoría sembrada por identificador: la siembra repetida no duplica.
    Index(
        "uq_categories_owner_id_slug",
        "owner_id",
        "slug",
        unique=True,
        postgresql_where=text("slug IS NOT NULL"),
    ),
)

# Una compra en cuotas (ADR-0026). Cada cuota se vuelve un movimiento al llegar
# su fecha, y la clave foránea de ese movimiento apunta a (id, dueño, cuenta,
# cantidad): la base garantiza que la cuota es del mismo plan, de la misma
# persona y de la misma cuenta, y que su número no pasa de la cantidad.
installment_plans = Table(
    "installment_plans",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("account_id", Uuid, nullable=False),
    Column("currency", String(3), nullable=False),
    # Siempre un gasto: está para que la clave foránea exija una categoría de gastos.
    Column("kind", String(8), nullable=False),
    Column("category_id", Uuid, nullable=False),
    Column("total", Numeric(20, 8), nullable=False),
    Column("count", SmallInteger, nullable=False),
    Column("first_on", Date, nullable=False),
    Column("description", String(120), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("cancelled_at", DateTime(timezone=True), nullable=True),
    ForeignKeyConstraint(
        ["account_id", "owner_id", "currency"],
        ["accounts.id", "accounts.owner_id", "accounts.currency"],
        name="account_of_the_same_owner_and_currency",
    ),
    ForeignKeyConstraint(
        ["category_id", "owner_id", "kind"],
        ["categories.id", "categories.owner_id", "categories.kind"],
        name="category_of_the_same_owner_and_kind",
    ),
    CheckConstraint("kind = 'expense'", name="is_an_expense"),
    CheckConstraint("count BETWEEN 2 AND 48", name="count_in_range"),
    CheckConstraint("total > 0", name="total_positive"),
    CheckConstraint("currency = 'BTC' OR total = round(total, 2)", name="total_fits_the_currency"),
    # Cada cuota es de al menos la unidad mínima de su moneda.
    CheckConstraint(
        "total >= count * CASE WHEN currency = 'BTC' THEN 0.00000001 ELSE 0.01 END",
        name="every_installment_has_a_minimum",
    ),
    CheckConstraint(
        "cancelled_at IS NULL OR cancelled_at >= created_at", name="cancelled_after_created"
    ),
    Index(
        "uq_installment_plans_id_owner_account_count",
        "id",
        "owner_id",
        "account_id",
        "count",
        unique=True,
    ),
    Index("ix_installment_plans_owner_id_first_on", "owner_id", text("first_on DESC")),
    Index("ix_installment_plans_category_id", "category_id"),
)

transactions = Table(
    "transactions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("account_id", Uuid, nullable=False),
    # La moneda se guarda al lado del monto y la clave foránea la ata a la de la
    # cuenta: un gasto en dólares no puede entrar en una caja en pesos (ADR-0011).
    Column("currency", String(3), nullable=False),
    Column("kind", String(8), nullable=False),
    Column("amount", Numeric(20, 8), nullable=False),
    Column("category_id", Uuid, nullable=False),
    Column("occurred_on", Date, nullable=False),
    Column("description", String(120), nullable=True),
    # La misma descripción sin tildes y en minúsculas: es lo que se compara al
    # buscar. Se guarda en lugar de plegarla en cada consulta, que obligaría a
    # recorrer la tabla entera aplicando una función a cada fila.
    Column("description_search", String(120), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    # Solo en los importados: SHA-256 de la línea del archivo, en hexadecimal (ADR-0023).
    Column("source_fingerprint", String(64), nullable=True),
    # Solo en las cuotas: de qué plan, cuál y de cuántas (ADR-0026).
    Column("installment_plan_id", Uuid, nullable=True),
    Column("installment_number", SmallInteger, nullable=True),
    Column("installment_count", SmallInteger, nullable=True),
    ForeignKeyConstraint(
        ["account_id", "owner_id", "currency"],
        ["accounts.id", "accounts.owner_id", "accounts.currency"],
        name="account_of_the_same_owner_and_currency",
    ),
    ForeignKeyConstraint(
        ["installment_plan_id", "owner_id", "account_id", "installment_count"],
        [
            "installment_plans.id",
            "installment_plans.owner_id",
            "installment_plans.account_id",
            "installment_plans.count",
        ],
        name="installment_of_the_same_plan_owner_and_account",
    ),
    CheckConstraint(
        "(installment_plan_id IS NULL) = (installment_number IS NULL)"
        " AND (installment_plan_id IS NULL) = (installment_count IS NULL)",
        name="installment_complete",
    ),
    CheckConstraint(
        "installment_number IS NULL OR installment_number BETWEEN 1 AND installment_count",
        name="installment_number_in_range",
    ),
    CheckConstraint(
        "installment_plan_id IS NULL OR kind = 'expense'", name="installment_is_an_expense"
    ),
    # Cada cuota se genera una sola vez, aunque después se borre: borrarla fue
    # una decisión, y generar lo vencido no la deshace (ADR-0026).
    Index(
        "uq_transactions_installment_plan_id_number",
        "installment_plan_id",
        "installment_number",
        unique=True,
        postgresql_where=text("installment_plan_id IS NOT NULL"),
    ),
    ForeignKeyConstraint(
        ["category_id", "owner_id", "kind"],
        ["categories.id", "categories.owner_id", "categories.kind"],
        name="category_of_the_same_owner_and_kind",
    ),
    CheckConstraint("amount > 0", name="amount_positive"),
    # Cada moneda tiene su precisión: 2 decimales, salvo Bitcoin, que admite 8.
    CheckConstraint(
        "currency = 'BTC' OR amount = round(amount, 2)", name="amount_fits_the_currency"
    ),
    CheckConstraint(f"kind IN {_KINDS}", name="kind_known"),
    CheckConstraint("deleted_at IS NULL OR deleted_at >= created_at", name="deleted_after_created"),
    CheckConstraint("updated_at >= created_at", name="updated_after_created"),
    # Índices parciales: las lecturas solo miran los movimientos vivos (ADR-0011).
    Index(
        "ix_transactions_owner_id_occurred_on",
        "owner_id",
        text("occurred_on DESC"),
        text("id DESC"),
        postgresql_where=text("deleted_at IS NULL"),
    ),
    Index(
        "ix_transactions_owner_id_account_id_occurred_on",
        "owner_id",
        "account_id",
        text("occurred_on DESC"),
        text("id DESC"),
        postgresql_where=text("deleted_at IS NULL"),
    ),
    Index(
        "ix_transactions_category_id",
        "category_id",
        postgresql_where=text("deleted_at IS NULL"),
    ),
    CheckConstraint(
        "source_fingerprint IS NULL OR source_fingerprint ~ '^[0-9a-f]{64}$'",
        name="source_fingerprint_is_sha256",
    ),
    # Una línea se importa una sola vez por cuenta, aunque después se borre el
    # movimiento: borrarlo fue una decisión, y reimportar no la deshace.
    Index(
        "uq_transactions_account_id_source_fingerprint",
        "account_id",
        "source_fingerprint",
        unique=True,
        postgresql_where=text("source_fingerprint IS NOT NULL"),
    ),
)

# Append-only: un disparador rechaza actualizar y borrar (ADR-0011).
transaction_audit = Table(
    "transaction_audit",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("transaction_id", Uuid, nullable=False),
    Column("owner_id", Uuid, nullable=False),
    Column("action", String(16), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    # Cómo quedó el movimiento después de la acción, para poder reconstruir la historia.
    Column("snapshot", JSONB, nullable=False),
    CheckConstraint(
        "action IN ('registered', 'edited', 'deleted', 'restored')", name="action_known"
    ),
    Index("ix_transaction_audit_transaction_id_recorded_at", "transaction_id", "recorded_at"),
)

idempotency_keys = Table(
    "idempotency_keys",
    metadata,
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("key", String(255), primary_key=True),
    Column("fingerprint", String(64), nullable=False),
    # Qué creó la clave. Se guarda en lugar de deducirlo: la misma clave usada
    # para un movimiento y para una transferencia tiene que fallar de forma
    # evidente, y no depender de que las huellas casualmente no coincidan.
    Column("resource", String(16), nullable=False),
    Column("resource_id", Uuid, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "resource IN ('transaction', 'transfer', 'installment_plan')", name="resource_known"
    ),
    Index("ix_idempotency_keys_created_at", "created_at"),
)


# Una transferencia entre dos cuentas propias: no es gasto ni ingreso (ADR-0014).
transfers = Table(
    "transfers",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    # Cada lado lleva su moneda al lado de su monto, y la clave foránea compuesta
    # la ata a la de su cuenta: la base garantiza que lo que sale está en la
    # moneda de la cuenta que envía y lo que entra en la de la que recibe.
    Column("from_account_id", Uuid, nullable=False),
    Column("currency_out", String(3), nullable=False),
    Column("amount_out", Numeric(20, 8), nullable=False),
    Column("to_account_id", Uuid, nullable=False),
    Column("currency_in", String(3), nullable=False),
    Column("amount_in", Numeric(20, 8), nullable=False),
    Column("occurred_on", Date, nullable=False),
    Column("description", String(120), nullable=True),
    # Igual que en movimientos: la forma comparable, para buscar.
    Column("description_search", String(120), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    ForeignKeyConstraint(
        ["from_account_id", "owner_id", "currency_out"],
        ["accounts.id", "accounts.owner_id", "accounts.currency"],
        name="origin_of_the_same_owner_and_currency",
    ),
    ForeignKeyConstraint(
        ["to_account_id", "owner_id", "currency_in"],
        ["accounts.id", "accounts.owner_id", "accounts.currency"],
        name="destination_of_the_same_owner_and_currency",
    ),
    # Mover plata de una cuenta a sí misma no es nada.
    CheckConstraint("from_account_id <> to_account_id", name="different_accounts"),
    # Los dos lados son positivos: la dirección la dan origen y destino.
    CheckConstraint("amount_out > 0 AND amount_in > 0", name="amounts_positive"),
    CheckConstraint(
        "currency_out = 'BTC' OR amount_out = round(amount_out, 2)",
        name="amount_out_fits_the_currency",
    ),
    CheckConstraint(
        "currency_in = 'BTC' OR amount_in = round(amount_in, 2)",
        name="amount_in_fits_the_currency",
    ),
    CheckConstraint("deleted_at IS NULL OR deleted_at >= created_at", name="deleted_after_created"),
    CheckConstraint("updated_at >= created_at", name="updated_after_created"),
    # Mismo orden que los movimientos: las dos listas se ordenan por el mismo par
    # para poder unirse más adelante (ADR-0014, decisión 5).
    Index(
        "ix_transfers_owner_id_occurred_on",
        "owner_id",
        text("occurred_on DESC"),
        text("id DESC"),
        postgresql_where=text("deleted_at IS NULL"),
    ),
    # La cuenta filtra de los dos lados, así que lleva un índice por lado.
    Index(
        "ix_transfers_owner_id_from_account_id_occurred_on",
        "owner_id",
        "from_account_id",
        text("occurred_on DESC"),
        text("id DESC"),
        postgresql_where=text("deleted_at IS NULL"),
    ),
    Index(
        "ix_transfers_owner_id_to_account_id_occurred_on",
        "owner_id",
        "to_account_id",
        text("occurred_on DESC"),
        text("id DESC"),
        postgresql_where=text("deleted_at IS NULL"),
    ),
)


# Append-only, igual que el de movimientos (ADR-0014, decisión 4).
transfer_audit = Table(
    "transfer_audit",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("transfer_id", Uuid, nullable=False),
    Column("owner_id", Uuid, nullable=False),
    Column("action", String(16), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("snapshot", JSONB, nullable=False),
    CheckConstraint(
        "action IN ('registered', 'edited', 'deleted', 'restored')", name="action_known"
    ),
    Index("ix_transfer_audit_transfer_id_recorded_at", "transfer_id", "recorded_at"),
)
