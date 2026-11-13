"""Implementaciones en memoria de los puertos, para tests sin infraestructura."""

from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from rinde.accounts.application.unit import AccountsUnit, build_accounts_unit
from rinde.accounts.application.use_cases import AccountsDependencies, GetAccount
from rinde.accounts.domain.account import Account
from rinde.alerts.application.unit import AlertsGateways, AlertsUnit, build_alerts_unit
from rinde.alerts.infrastructure.gateways import BudgetsMonthReader
from rinde.alerts.infrastructure.gateways import (
    TransactionsCategoryReader as AlertsCategoryReader,
)
from rinde.auth.application.dependencies import AuthDependencies, AuthServices
from rinde.auth.application.ports import ClientAction, Session
from rinde.auth.application.unit import AuthUnit, build_auth_unit
from rinde.auth.domain.errors import UsernameTakenError
from rinde.auth.domain.user import User
from rinde.auth.domain.username import Username
from rinde.budgets.application.unit import BudgetsGateways, BudgetsUnit, build_budgets_unit
from rinde.budgets.infrastructure.gateways import (
    PreferencesRateTypeReader,
    RatesConverterFactory,
    TransactionsCategoryReader,
    TransactionsSpendingReader,
)
from rinde.imports.application.unit import ImportsGateways, ImportsUnit, build_imports_unit
from rinde.imports.infrastructure.gateways import (
    TransactionsAccountInspector,
    TransactionsRegistrar,
)
from rinde.imports.infrastructure.gateways import (
    TransactionsCategoryReader as ImportsCategoryReader,
)
from rinde.preferences.application.unit import PreferencesUnit, build_preferences_unit
from rinde.preferences.application.use_cases import PreferencesDependencies
from rinde.preferences.domain.preferences import Preferences
from rinde.rates.application.unit import RatesUnit, build_rates_unit
from rinde.rates.application.use_cases import RatesDependencies
from rinde.transactions.application.dependencies import TransactionsDependencies
from rinde.transactions.application.ports import EventPublisher
from rinde.transactions.application.unit import TransactionsUnit, build_transactions_unit
from rinde.transactions.infrastructure.accounts_gateway import AccountsApplicationGateway
from tests.unit.alerts.fakes import InMemoryAlertRepository
from tests.unit.budgets.fakes import InMemoryBudgetRepository
from tests.unit.imports.fakes import InMemoryBatchRepository
from tests.unit.rates.fakes import FakeHistoryProvider, FakeRateProvider, InMemoryQuotes
from tests.unit.transactions.fakes import (
    FakeAuditLog,
    FakeCategoryRepository,
    FakeIdempotencyStore,
    FakeTransactionRepository,
    FakeTransferAuditLog,
    FakeTransferRepository,
    RecordingPublisher,
)


class FakeDatabaseProbe:
    def __init__(self, *, reachable: bool) -> None:
        self.reachable = reachable
        self.calls = 0

    async def is_reachable(self) -> bool:
        self.calls += 1
        return self.reachable


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 9, 11, 12, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


class FakeHasher:
    """Hash legible para tests. `version` simula un cambio de parámetros del algoritmo."""

    dummy_hash = "hash:dummy"

    def __init__(self) -> None:
        self.version = 1
        self.verify_calls = 0

    async def hash(self, secret: str) -> str:
        return f"hash:v{self.version}:{secret}"

    async def verify(self, secret_hash: str, secret: str) -> bool:
        self.verify_calls += 1
        parts = secret_hash.split(":", 2)
        return len(parts) == 3 and parts[1].startswith("v") and parts[2] == secret

    def needs_rehash(self, secret_hash: str) -> bool:
        return not secret_hash.startswith(f"hash:v{self.version}:")


class FakeBreachChecker:
    def __init__(self, compromised: Iterable[str] = ()) -> None:
        self.compromised = set(compromised)

    async def is_compromised(self, password: str) -> bool:
        return password in self.compromised


class FakeSecrets:
    def __init__(self) -> None:
        self._counter = 0

    def recovery_code(self) -> str:
        self._counter += 1
        return f"{self._counter:020d}"

    def session_token(self) -> str:
        self._counter += 1
        return f"token-{self._counter}"


class InMemoryUsers:
    def __init__(self) -> None:
        self.store: dict[UUID, User] = {}

    async def add(self, user: User) -> None:
        if any(existing.username == user.username for existing in self.store.values()):
            raise UsernameTakenError
        self.store[user.id] = user

    async def by_username(self, username: Username) -> User | None:
        return next((user for user in self.store.values() if user.username == username), None)

    async def by_id(self, user_id: UUID) -> User | None:
        return self.store.get(user_id)

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        self.store[user_id] = replace(self.store[user_id], password_hash=password_hash)

    async def update_credentials(
        self, user_id: UUID, *, password_hash: str, recovery_code_hash: str
    ) -> None:
        self.store[user_id] = replace(
            self.store[user_id],
            password_hash=password_hash,
            recovery_code_hash=recovery_code_hash,
        )


class InMemorySessions:
    def __init__(self) -> None:
        self.store: dict[str, Session] = {}

    async def add(self, session: Session) -> None:
        self.store[session.token_hash] = session

    async def by_token_hash(self, token_hash: str) -> Session | None:
        return self.store.get(token_hash)

    async def delete(self, token_hash: str) -> None:
        self.store.pop(token_hash, None)

    async def delete_all_for_user(self, user_id: UUID) -> None:
        self.store = {key: s for key, s in self.store.items() if s.user_id != user_id}


class InMemoryFailedAttempts:
    def __init__(self) -> None:
        self.attempts: list[tuple[Username, datetime]] = []

    async def count_since(self, username: Username, since: datetime) -> int:
        return sum(1 for who, at in self.attempts if who == username and at >= since)

    async def record(self, username: Username, at: datetime) -> None:
        self.attempts.append((username, at))

    async def clear(self, username: Username) -> None:
        self.attempts = [(who, at) for who, at in self.attempts if who != username]

    async def purge_before(self, cutoff: datetime) -> None:
        self.attempts = [(who, at) for who, at in self.attempts if at >= cutoff]


class InMemoryClientActivity:
    def __init__(self) -> None:
        self.events: list[tuple[ClientAction, str, datetime]] = []

    async def count_since(self, action: ClientAction, client: str, since: datetime) -> int:
        return sum(
            1 for what, who, at in self.events if what == action and who == client and at >= since
        )

    async def record(self, action: ClientAction, client: str, at: datetime) -> None:
        self.events.append((action, client, at))

    async def purge_before(self, cutoff: datetime) -> None:
        self.events = [(what, who, at) for what, who, at in self.events if at >= cutoff]


class FakeTransaction:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class InMemoryAuthUnitFactory:
    """Estado compartido entre pedidos, como si fuera la base de datos."""

    def __init__(self, *, compromised: Iterable[str] = ()) -> None:
        self.users = InMemoryUsers()
        self.sessions = InMemorySessions()
        self.failed_attempts = InMemoryFailedAttempts()
        self.client_activity = InMemoryClientActivity()
        self.transaction = FakeTransaction()
        self.hasher = FakeHasher()
        self.clock = FakeClock()
        self.services = AuthServices(
            hasher=self.hasher,
            breaches=FakeBreachChecker(compromised),
            clock=self.clock,
            secrets=FakeSecrets(),
            session_ttl=timedelta(days=30),
        )

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AuthUnit]:
        yield build_auth_unit(
            AuthDependencies(
                users=self.users,
                sessions=self.sessions,
                failed_attempts=self.failed_attempts,
                client_activity=self.client_activity,
                transaction=self.transaction,
                services=self.services,
            )
        )


class InMemoryAccounts:
    def __init__(self) -> None:
        self.rows: dict[UUID, Account] = {}

    async def add(self, account: Account) -> None:
        self.rows[account.id] = account

    async def get(self, account_id: UUID, owner_id: UUID) -> Account | None:
        account = self.rows.get(account_id)
        return account if account and account.owner_id == owner_id else None

    async def list_for_owner(self, owner_id: UUID, *, include_archived: bool) -> list[Account]:
        return sorted(
            (
                account
                for account in self.rows.values()
                if account.owner_id == owner_id and (include_archived or not account.is_archived)
            ),
            key=lambda account: (account.created_at, account.id),
        )

    async def save(self, account: Account) -> None:
        self.rows[account.id] = account


class InMemoryAccountsUnitFactory:
    """Estado compartido entre pedidos, como si fuera la base de datos."""

    def __init__(self, clock: FakeClock | None = None) -> None:
        self.accounts = InMemoryAccounts()
        self.transaction = FakeTransaction()
        self.clock = clock or FakeClock()

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AccountsUnit]:
        yield build_accounts_unit(
            AccountsDependencies(
                accounts=self.accounts, transaction=self.transaction, clock=self.clock
            )
        )


class InMemoryTransactionsUnitFactory:
    """Estado compartido entre pedidos, como si fuera la base de datos.

    Las cuentas las ve por el mismo adaptador que en producción, así los tests
    de API prueban también ese camino.
    """

    def __init__(
        self,
        accounts: InMemoryAccounts,
        clock: FakeClock | None = None,
        events: EventPublisher | None = None,
    ) -> None:
        self.transactions = FakeTransactionRepository()
        self.transfers = FakeTransferRepository()
        self.categories = FakeCategoryRepository()
        self.idempotency = FakeIdempotencyStore()
        self.audit = FakeAuditLog()
        self.transfer_audit = FakeTransferAuditLog()
        self.transaction = FakeTransaction()
        self.clock = clock or FakeClock()
        self._accounts = accounts
        # Por defecto guarda lo publicado; los tests de alertas le pasan el bus real.
        self.events = events or RecordingPublisher()

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[TransactionsUnit]:
        yield build_transactions_unit(
            TransactionsDependencies(
                transactions=self.transactions,
                transfers=self.transfers,
                categories=self.categories,
                accounts=AccountsApplicationGateway(
                    GetAccount(
                        AccountsDependencies(
                            accounts=self._accounts,
                            transaction=self.transaction,
                            clock=self.clock,
                        )
                    )
                ),
                idempotency=self.idempotency,
                audit=self.audit,
                transfer_audit=self.transfer_audit,
                transaction=self.transaction,
                clock=self.clock,
                events=self.events,
            )
        )


class InMemoryRatesUnitFactory:
    """Cotizaciones con fuentes y base en memoria, compartidas entre pedidos."""

    def __init__(
        self,
        provider: FakeRateProvider | None = None,
        history: FakeHistoryProvider | None = None,
    ) -> None:
        self.provider = provider or FakeRateProvider()
        self.history = history or FakeHistoryProvider()
        self.quotes = InMemoryQuotes()
        self.transaction = FakeTransaction()
        self.clock = FakeClock()
        # Las 12 de Buenos Aires del 10 de noviembre de 2026.
        self.clock.current = datetime(2026, 11, 10, 15, tzinfo=UTC)

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[RatesUnit]:
        yield build_rates_unit(
            RatesDependencies(
                quotes=self.quotes,
                provider=self.provider,
                history=self.history,
                transaction=self.transaction,
                clock=self.clock,
            )
        )


class InMemoryPreferences:
    def __init__(self) -> None:
        self.rows: dict[UUID, Preferences] = {}

    async def get(self, owner_id: UUID) -> Preferences | None:
        return self.rows.get(owner_id)

    async def save(self, preferences: Preferences) -> None:
        self.rows[preferences.owner_id] = preferences


class InMemoryPreferencesUnitFactory:
    """Preferencias en memoria, compartidas entre pedidos como si fuera la base."""

    def __init__(self) -> None:
        self.preferences = InMemoryPreferences()
        self.transaction = FakeTransaction()
        self.clock = FakeClock()

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[PreferencesUnit]:
        yield build_preferences_unit(
            PreferencesDependencies(
                preferences=self.preferences, transaction=self.transaction, clock=self.clock
            )
        )


class InMemoryBudgetsUnitFactory:
    """Presupuestos en memoria, con los adaptadores reales sobre los otros módulos en memoria."""

    def __init__(
        self,
        transactions: InMemoryTransactionsUnitFactory,
        preferences: InMemoryPreferencesUnitFactory,
        rates: InMemoryRatesUnitFactory,
        clock: FakeClock | None = None,
    ) -> None:
        self.budgets = InMemoryBudgetRepository()
        self.transaction = FakeTransaction()
        self.clock = clock or FakeClock()
        self._gateways = BudgetsGateways(
            categories=TransactionsCategoryReader(transactions),
            spending=TransactionsSpendingReader(transactions),
            rate_types=PreferencesRateTypeReader(preferences),
            converters=RatesConverterFactory(rates),
        )

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[BudgetsUnit]:
        yield build_budgets_unit(self.budgets, self.transaction, self._gateways, self.clock)


class InMemoryAlertsUnitFactory:
    """Alertas en memoria, con los adaptadores reales sobre presupuestos y movimientos."""

    def __init__(
        self,
        transactions: InMemoryTransactionsUnitFactory,
        budgets: InMemoryBudgetsUnitFactory,
        clock: FakeClock | None = None,
    ) -> None:
        self.alerts = InMemoryAlertRepository()
        self.transaction = FakeTransaction()
        self.clock = clock or FakeClock()
        self.gateways = AlertsGateways(
            budgets=BudgetsMonthReader(budgets),
            categories=AlertsCategoryReader(transactions),
        )

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AlertsUnit]:
        yield build_alerts_unit(self.alerts, self.transaction, self.gateways, self.clock)


class InMemoryImportsUnitFactory:
    """Lotes en memoria, con los adaptadores reales sobre movimientos en memoria."""

    def __init__(
        self, transactions: InMemoryTransactionsUnitFactory, clock: FakeClock | None = None
    ) -> None:
        self.batches = InMemoryBatchRepository()
        self.transaction = FakeTransaction()
        self.clock = clock or FakeClock()
        self.gateways = ImportsGateways(
            accounts=TransactionsAccountInspector(transactions),
            registrar=TransactionsRegistrar(transactions),
            categories=ImportsCategoryReader(transactions),
        )

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[ImportsUnit]:
        yield build_imports_unit(self.batches, self.transaction, self.gateways, self.clock)
