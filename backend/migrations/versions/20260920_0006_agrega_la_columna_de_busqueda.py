"""agrega la columna de busqueda

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-20

La columna guarda la descripción sin tildes y en minúsculas, que es lo que se
compara al buscar. Se rellena acá para las filas que ya existen: si no, una
descripción vieja sería invisible para el buscador, que es el peor error posible
en un filtro, porque no se nota.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from rinde.shared.domain.text import fold

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# El plegado vive en Python y no en la base, para no depender de qué extensiones
# permita el proveedor. El precio es este relleno, que hay que hacer una vez.
_TABLAS = ("transactions", "transfers")


def upgrade() -> None:
    for tabla in _TABLAS:
        op.add_column(tabla, sa.Column("description_search", sa.String(length=120), nullable=True))

    conexion = op.get_bind()
    for tabla in _TABLAS:
        filas = conexion.execute(
            sa.text(
                f"SELECT id, description FROM {tabla} WHERE description IS NOT NULL"  # noqa: S608
            )
        ).fetchall()
        for identificador, descripcion in filas:
            conexion.execute(
                sa.text(
                    f"UPDATE {tabla} SET description_search = :plegada WHERE id = :id"  # noqa: S608
                ),
                {"plegada": fold(descripcion), "id": identificador},
            )


def downgrade() -> None:
    for tabla in reversed(_TABLAS):
        op.drop_column(tabla, "description_search")
