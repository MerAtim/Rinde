"""La auditoría se borra con su dueño (ADR-0028).

Las dos auditorías pasan a tener clave foránea a `users` con borrado en
cascada, y su disparador deja pasar solo ese borrado: el de las filas de un
dueño que ya no existe. Cambiar una fila o borrarla a mano sigue fallando.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("transaction_audit", "transfer_audit")


def _guard(table: str, *, erasable: bool) -> str:
    # La cascada borra primero la fila de `users`: cuando el disparador corre,
    # el dueño ya no existe y el borrado pasa. Un DELETE directo lo encuentra.
    allow = (
        """
    IF TG_OP = 'DELETE' AND NOT EXISTS (SELECT 1 FROM users WHERE id = OLD.owner_id) THEN
        RETURN OLD;
    END IF;"""
        if erasable
        else ""
    )
    return f"""
CREATE OR REPLACE FUNCTION {table}_is_append_only() RETURNS trigger AS $$
BEGIN{allow}
    RAISE EXCEPTION '{table} es append-only: no se puede % una fila', TG_OP;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    for table in _TABLES:
        op.execute(_guard(table, erasable=True))
        op.create_foreign_key(
            op.f(f"fk_{table}_owner_id_users"),
            table,
            "users",
            ["owner_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(op.f(f"ix_{table}_owner_id"), table, ["owner_id"])


def downgrade() -> None:
    for table in _TABLES:
        op.drop_index(op.f(f"ix_{table}_owner_id"), table_name=table)
        op.drop_constraint(op.f(f"fk_{table}_owner_id_users"), table, type_="foreignkey")
        op.execute(_guard(table, erasable=False))
