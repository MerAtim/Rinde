"""Exportación con los módulos en memoria, por los mismos adaptadores que en producción."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from rinde.auth.domain.errors import NotAuthenticatedError
from rinde.privacy.application.records import FORMAT_VERSION, AccountRecord
from rinde.privacy.application.use_cases import ExportPersonalData, PrivacyDependencies
from rinde.privacy.infrastructure import gateways
from tests.fakes import (
    FakeClock,
    InMemoryAccountsUnitFactory,
    InMemoryAlertsUnitFactory,
    InMemoryAuthUnitFactory,
    InMemoryBudgetsUnitFactory,
    InMemoryImportsUnitFactory,
    InMemoryPreferencesUnitFactory,
    InMemoryRatesUnitFactory,
    InMemoryTransactionsUnitFactory,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)


class CountingAccounts(gateways.ModuleAccountsReader):
    """Cuenta las lecturas, para saber si se llegó a leer otro módulo."""

    calls = 0

    async def accounts(self, owner_id: UUID) -> list[AccountRecord]:
        type(self).calls += 1
        return await super().accounts(owner_id)


def _export(auth: InMemoryAuthUnitFactory) -> ExportPersonalData:
    clock = FakeClock()
    clock.current = NOW
    accounts = InMemoryAccountsUnitFactory(clock)
    transactions = InMemoryTransactionsUnitFactory(accounts.accounts, clock)
    preferences = InMemoryPreferencesUnitFactory()
    budgets = InMemoryBudgetsUnitFactory(
        transactions, preferences, InMemoryRatesUnitFactory(), clock
    )
    return ExportPersonalData(
        PrivacyDependencies(
            profile=gateways.AuthProfileReader(auth),
            preferences=gateways.ModulePreferencesReader(preferences),
            accounts=CountingAccounts(accounts),
            ledger=gateways.TransactionsLedgerReader(transactions),
            budgets=gateways.ModuleBudgetsReader(budgets),
            alerts=gateways.ModuleAlertsReader(
                InMemoryAlertsUnitFactory(transactions, budgets, clock)
            ),
            imports=gateways.ModuleImportsReader(InMemoryImportsUnitFactory(transactions, clock)),
            clock=clock,
        )
    )


async def test_una_cuenta_nueva_se_exporta_con_las_secciones_vacias() -> None:
    auth = InMemoryAuthUnitFactory()
    async with auth() as unit:
        await unit.register.execute("mechi", "mi gato come fideos los martes")
    [user] = auth.users.store.values()

    data = await _export(auth).execute(user.id)

    assert data.format_version == FORMAT_VERSION
    assert data.generated_at == NOW
    assert data.profile.username == "mechi"
    assert data.preferences.updated_at is None
    assert data.accounts == []
    assert data.ledger.transactions == []
    assert data.budgets == []
    assert data.alerts == []
    assert data.imports.batches == []


async def test_sin_la_cuenta_no_lee_ningun_otro_modulo() -> None:
    CountingAccounts.calls = 0

    with pytest.raises(NotAuthenticatedError):
        await _export(InMemoryAuthUnitFactory()).execute(uuid4())

    assert CountingAccounts.calls == 0
