"""Puertos de privacidad: lo que la exportación le pide a cada módulo.

Privacidad no tiene tablas propias. Lee a los otros módulos por su capa de
aplicación, con adaptadores que la raíz de composición arma, como el dashboard
(ADR-0018). Cada lectura es solo del dueño que recibe.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from rinde.privacy.application.records import (
    AccountRecord,
    AlertRecord,
    BudgetRecord,
    ImportRecords,
    LedgerRecords,
    PreferencesRecord,
    ProfileRecord,
)


class ProfileReader(Protocol):
    async def profile(self, owner_id: UUID) -> ProfileRecord: ...


class PreferencesReader(Protocol):
    async def preferences(self, owner_id: UUID) -> PreferencesRecord: ...


class AccountsReader(Protocol):
    async def accounts(self, owner_id: UUID) -> list[AccountRecord]:
        """Las archivadas también."""
        ...


class LedgerReader(Protocol):
    async def ledger(self, owner_id: UUID) -> LedgerRecords:
        """Lo borrado también, y el historial de cambios."""
        ...


class BudgetsReader(Protocol):
    async def budgets(self, owner_id: UUID) -> list[BudgetRecord]: ...


class AlertsReader(Protocol):
    async def alerts(self, owner_id: UUID) -> list[AlertRecord]: ...


class ImportsReader(Protocol):
    async def imports(self, owner_id: UUID) -> ImportRecords: ...


class Clock(Protocol):
    def now(self) -> datetime: ...
