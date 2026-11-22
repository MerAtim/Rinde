"""Caso de uso: exportar todos los datos de una persona (Ley 25.326, art. 14; ADR-0034).

Cada módulo se lee en su propia unidad de trabajo, uno después del otro: en un
pedido se usa una sola conexión a la vez. El costo aceptado es que las secciones
no salen de una misma foto de la base. Si la persona cambia algo mientras se
arma el archivo, ese cambio puede estar en una sección y no en otra. Para una
copia que pide la misma persona, eso no justifica una transacción entre módulos.
"""

from dataclasses import dataclass
from uuid import UUID

from rinde.privacy.application.ports import (
    AccountsReader,
    AlertsReader,
    BudgetsReader,
    Clock,
    ImportsReader,
    LedgerReader,
    PreferencesReader,
    ProfileReader,
)
from rinde.privacy.application.records import FORMAT_VERSION, PersonalData


@dataclass(frozen=True, slots=True)
class PrivacyDependencies:
    profile: ProfileReader
    preferences: PreferencesReader
    accounts: AccountsReader
    ledger: LedgerReader
    budgets: BudgetsReader
    alerts: AlertsReader
    imports: ImportsReader
    clock: Clock


class ExportPersonalData:
    def __init__(self, deps: PrivacyDependencies) -> None:
        self._deps = deps

    async def execute(self, owner_id: UUID) -> PersonalData:
        deps = self._deps
        # El perfil primero: si la cuenta ya no existe, no se lee nada más.
        profile = await deps.profile.profile(owner_id)
        return PersonalData(
            format_version=FORMAT_VERSION,
            generated_at=deps.clock.now(),
            profile=profile,
            preferences=await deps.preferences.preferences(owner_id),
            accounts=await deps.accounts.accounts(owner_id),
            ledger=await deps.ledger.ledger(owner_id),
            budgets=await deps.budgets.budgets(owner_id),
            alerts=await deps.alerts.alerts(owner_id),
            imports=await deps.imports.imports(owner_id),
        )
