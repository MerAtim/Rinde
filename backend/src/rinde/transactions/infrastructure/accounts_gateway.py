"""Adaptador hacia cuentas: la única puerta por la que movimientos ve una cuenta.

Pasa por el caso de uso de cuentas, no por sus tablas. Si mañana cuentas cambia
su modelo, el impacto llega hasta acá y no más adentro.
"""

from uuid import UUID

from rinde.accounts.application.use_cases import GetAccount
from rinde.accounts.domain.errors import AccountNotFoundError
from rinde.shared.domain.money import Currency
from rinde.transactions.domain.transaction import TargetAccount


class AccountsApplicationGateway:
    def __init__(self, get_account: GetAccount) -> None:
        self._get_account = get_account

    async def target(self, account_id: UUID, owner_id: UUID) -> TargetAccount | None:
        try:
            account = await self._get_account.execute(owner_id, account_id)
        except AccountNotFoundError:
            # Una cuenta ajena o inexistente es lo mismo para quien pregunta (ADR-0009).
            return None
        return TargetAccount(
            id=account.id,
            currency=Currency(account.currency),
            is_archived=account.is_archived,
        )
