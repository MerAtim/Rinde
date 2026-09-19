"""crea transferencias

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-19

Las reglas del dominio se repiten como restricciones de la base (ADR-0014): si
alguien escribe una fila sin pasar por el dominio, la base la rechaza igual.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# El log de auditoría solo admite inserciones: la regla vale también desde psql.
_AUDIT_GUARD = """
CREATE OR REPLACE FUNCTION transfer_audit_is_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'transfer_audit es append-only: no se puede % una fila', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER transfer_audit_no_update_or_delete
BEFORE UPDATE OR DELETE ON transfer_audit
FOR EACH ROW EXECUTE FUNCTION transfer_audit_is_append_only();
"""


def upgrade() -> None:
    op.create_table(
        "transfer_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transfer_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "action IN ('registered', 'edited', 'deleted', 'restored')",
            name=op.f("ck_transfer_audit_action_known"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transfer_audit")),
    )
    op.create_index(
        "ix_transfer_audit_transfer_id_recorded_at",
        "transfer_audit",
        ["transfer_id", "recorded_at"],
        unique=False,
    )

    op.create_table(
        "transfers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("from_account_id", sa.Uuid(), nullable=False),
        sa.Column("currency_out", sa.String(length=3), nullable=False),
        sa.Column("amount_out", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("to_account_id", sa.Uuid(), nullable=False),
        sa.Column("currency_in", sa.String(length=3), nullable=False),
        sa.Column("amount_in", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "currency_in = 'BTC' OR amount_in = round(amount_in, 2)",
            name=op.f("ck_transfers_amount_in_fits_the_currency"),
        ),
        sa.CheckConstraint(
            "currency_out = 'BTC' OR amount_out = round(amount_out, 2)",
            name=op.f("ck_transfers_amount_out_fits_the_currency"),
        ),
        sa.CheckConstraint(
            "amount_out > 0 AND amount_in > 0", name=op.f("ck_transfers_amounts_positive")
        ),
        sa.CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name=op.f("ck_transfers_deleted_after_created"),
        ),
        sa.CheckConstraint(
            "from_account_id <> to_account_id", name=op.f("ck_transfers_different_accounts")
        ),
        sa.CheckConstraint(
            "updated_at >= created_at", name=op.f("ck_transfers_updated_after_created")
        ),
        # Cada lado apunta a (cuenta, dueño, moneda): así la base garantiza que
        # lo que sale está en la moneda de la cuenta que envía, y lo que entra
        # en la de la que recibe.
        sa.ForeignKeyConstraint(
            ["from_account_id", "owner_id", "currency_out"],
            ["accounts.id", "accounts.owner_id", "accounts.currency"],
            name="origin_of_the_same_owner_and_currency",
        ),
        sa.ForeignKeyConstraint(
            ["to_account_id", "owner_id", "currency_in"],
            ["accounts.id", "accounts.owner_id", "accounts.currency"],
            name="destination_of_the_same_owner_and_currency",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_transfers_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transfers")),
    )
    # Índices parciales: las lecturas solo miran las transferencias vivas, y el
    # orden es el mismo que el de los movimientos para poder unir las dos listas.
    op.create_index(
        "ix_transfers_owner_id_occurred_on",
        "transfers",
        ["owner_id", sa.literal_column("occurred_on DESC"), sa.literal_column("id DESC")],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_transfers_owner_id_from_account_id_occurred_on",
        "transfers",
        [
            "owner_id",
            "from_account_id",
            sa.literal_column("occurred_on DESC"),
            sa.literal_column("id DESC"),
        ],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_transfers_owner_id_to_account_id_occurred_on",
        "transfers",
        [
            "owner_id",
            "to_account_id",
            sa.literal_column("occurred_on DESC"),
            sa.literal_column("id DESC"),
        ],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # La columna se renombra, no se borra y se recrea: las claves ya guardadas
    # apuntan a movimientos reales, y perderlas dejaría un reintento sin su
    # resultado, que es justo lo que la idempotencia existe para evitar.
    op.alter_column("idempotency_keys", "transaction_id", new_column_name="resource_id")
    # Todo lo guardado hasta ahora fue un movimiento: el valor por defecto llena
    # las filas que ya existen y después se saca, para que toda fila nueva tenga
    # que decir explícitamente qué creó.
    op.add_column(
        "idempotency_keys",
        sa.Column("resource", sa.String(length=16), nullable=False, server_default="transaction"),
    )
    op.alter_column("idempotency_keys", "resource", server_default=None)
    op.create_check_constraint(
        op.f("ck_idempotency_keys_resource_known"),
        "idempotency_keys",
        "resource IN ('transaction', 'transfer')",
    )

    op.execute(_AUDIT_GUARD)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS transfer_audit_no_update_or_delete ON transfer_audit")
    op.execute("DROP FUNCTION IF EXISTS transfer_audit_is_append_only()")

    op.drop_constraint(
        op.f("ck_idempotency_keys_resource_known"), "idempotency_keys", type_="check"
    )
    op.drop_column("idempotency_keys", "resource")
    op.alter_column("idempotency_keys", "resource_id", new_column_name="transaction_id")

    op.drop_index(
        "ix_transfers_owner_id_to_account_id_occurred_on",
        table_name="transfers",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index(
        "ix_transfers_owner_id_from_account_id_occurred_on",
        table_name="transfers",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index(
        "ix_transfers_owner_id_occurred_on",
        table_name="transfers",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_table("transfers")
    op.drop_index("ix_transfer_audit_transfer_id_recorded_at", table_name="transfer_audit")
    op.drop_table("transfer_audit")
