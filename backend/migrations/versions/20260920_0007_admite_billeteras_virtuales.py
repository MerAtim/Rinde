"""admite billeteras virtuales

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-20

Mercado Pago, Ualá y Naranja X son un tipo de cuenta propio. Hasta ahora había
que cargarlas como efectivo, que funciona para el saldo pero miente sobre qué es
la cuenta.

Alembic no detecta los cambios en restricciones CHECK, así que esta migración se
escribe a mano: la generada salía vacía.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANTES = "kind IN ('cash', 'bank', 'credit_card', 'crypto_wallet')"
_DESPUES = "kind IN ('cash', 'bank', 'credit_card', 'virtual_wallet', 'crypto_wallet')"

# Bitcoin sigue solo en billeteras cripto: esa restricción es otra y no se toca,
# así que una billetera virtual en BTC se rechaza sin agregar nada (ADR-0009).
_NOMBRE = "ck_accounts_kind_known"


def _reemplazar(condicion: str) -> None:
    op.drop_constraint(op.f(_NOMBRE), "accounts", type_="check")
    op.create_check_constraint(op.f(_NOMBRE), "accounts", condicion)


def upgrade() -> None:
    _reemplazar(_DESPUES)


def downgrade() -> None:
    """Falla a propósito si ya hay billeteras virtuales cargadas.

    PostgreSQL valida la restricción contra las filas existentes al crearla. Si
    alguien ya abrió una cuenta de este tipo, volver atrás le borraría el dato o
    lo dejaría inválido: es mejor que la reversión se niegue y haya que decidir
    qué hacer con esas cuentas.
    """
    _reemplazar(_ANTES)
