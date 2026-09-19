"""La transferencia entre dos cuentas propias (ADR-0014).

Mover plata de una cuenta a otra no es un gasto ni un ingreso: el patrimonio no
cambia, cambia de lugar. Por eso es una entidad propia y no dos movimientos: un
reporte que lea movimientos es correcto por construcción, sin depender de que
cada consulta se acuerde de excluirla.

Los dos lados guardan su monto y su moneda. Entre monedas distintas no se
convierte nada: la tasa real es la que le dieron a la persona, y queda guardada
exacta en los dos montos.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime
from uuid import UUID

from rinde.shared.domain.money import Money
from rinde.transactions.domain.errors import (
    TransferAmountNotPositiveError,
    TransferCurrencyMismatchError,
    TransferDateInFutureError,
    TransferDeletedError,
    TransferSameAccountError,
)
from rinde.transactions.domain.transaction import (
    FUTURE_TOLERANCE,
    Description,
    TargetAccount,
)


@dataclass(frozen=True, slots=True)
class TransferRoute:
    """De qué cuenta a qué cuenta.

    Que no sean la misma es una invariante del tipo y no un chequeo que haya que
    acordarse de hacer: una ruta hacia la misma cuenta no se puede construir.
    """

    origin: TargetAccount
    destination: TargetAccount

    def __post_init__(self) -> None:
        if self.origin.id == self.destination.id:
            raise TransferSameAccountError


@dataclass(frozen=True, slots=True)
class TransferDraft:
    """Lo que la persona carga. Registrar y editar validan lo mismo, acá."""

    sent: Money
    """Lo que sale de la cuenta de origen, en la moneda de esa cuenta."""
    received: Money
    """Lo que entra en la de destino. Puede diferir: comisión, o cambio de moneda."""
    occurred_on: date
    description: Description | None = None

    def check(self, route: TransferRoute, at: datetime) -> None:
        if not self.sent.is_positive or not self.received.is_positive:
            raise TransferAmountNotPositiveError
        if self.sent.currency is not route.origin.currency:
            raise TransferCurrencyMismatchError
        if self.received.currency is not route.destination.currency:
            raise TransferCurrencyMismatchError
        if self.occurred_on > (at + FUTURE_TOLERANCE).date():
            raise TransferDateInFutureError


@dataclass(frozen=True, slots=True)
class Transfer:
    id: UUID
    owner_id: UUID
    from_account_id: UUID
    to_account_id: UUID
    sent: Money
    received: Money
    occurred_on: date
    """Fecha de valor: cuándo pasó, que no siempre es cuándo se anotó."""
    created_at: datetime
    updated_at: datetime
    description: Description | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        # En toda transferencia, no solo al registrarla: también en la que se lee
        # de la base. La dirección la dan origen y destino, nunca el signo.
        if not self.sent.is_positive or not self.received.is_positive:
            raise TransferAmountNotPositiveError
        if self.from_account_id == self.to_account_id:
            raise TransferSameAccountError

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def effect_on(self, account_id: UUID) -> Money | None:
        """Lo que le suma a una cuenta, o `None` si no la toca.

        Una transferencia borrada no mueve ningún saldo. Devolver `None` en vez
        de cero obliga a distinguir "no participa" de "participa con cero", que
        no puede pasar porque los dos lados son positivos.
        """
        if self.is_deleted:
            return None
        if account_id == self.from_account_id:
            return -self.sent
        if account_id == self.to_account_id:
            return self.received
        return None

    def edited(self, draft: TransferDraft, route: TransferRoute, *, at: datetime) -> Transfer:
        """Edita todo junto: las reglas cruzan los campos y se validan de una."""
        if self.is_deleted:
            raise TransferDeletedError
        draft.check(route, at)
        return replace(
            self,
            from_account_id=route.origin.id,
            to_account_id=route.destination.id,
            sent=draft.sent,
            received=draft.received,
            occurred_on=draft.occurred_on,
            description=draft.description,
            updated_at=at,
        )

    def deleted(self, at: datetime) -> Transfer:
        """Idempotente: borrar dos veces conserva la primera fecha (ADR-0011)."""
        return self if self.is_deleted else replace(self, deleted_at=at, updated_at=at)

    def restored(self, at: datetime) -> Transfer:
        """Deshacer un borrado, mientras la persona sigue mirando la pantalla."""
        return self if not self.is_deleted else replace(self, deleted_at=None, updated_at=at)


def register_transfer(
    draft: TransferDraft, route: TransferRoute, *, transfer_id: UUID, owner_id: UUID, at: datetime
) -> Transfer:
    """Crea una transferencia válida o no la crea."""
    draft.check(route, at)
    return Transfer(
        id=transfer_id,
        owner_id=owner_id,
        from_account_id=route.origin.id,
        to_account_id=route.destination.id,
        sent=draft.sent,
        received=draft.received,
        occurred_on=draft.occurred_on,
        created_at=at,
        updated_at=at,
        description=draft.description,
    )
