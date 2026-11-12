"""Raíz de composición: arma la aplicación y conecta cada puerto con su adaptador."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from importlib.metadata import version

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from rinde.accounts.api.errors import accounts_error_handler
from rinde.accounts.api.router import router as accounts_router
from rinde.accounts.application.unit import AccountsUnitFactory
from rinde.accounts.application.use_cases import AccountsDependencies, GetAccount
from rinde.accounts.domain.errors import AccountError
from rinde.accounts.infrastructure.factory import (
    SqlAlchemyAccountsUnitFactory,
    SqlAlchemyTransaction,
)
from rinde.accounts.infrastructure.repositories import SqlAlchemyAccountRepository
from rinde.auth.api.cookies import SessionCookie
from rinde.auth.api.errors import auth_error_handler
from rinde.auth.api.identity import identify_user
from rinde.auth.api.router import router as auth_router
from rinde.auth.application.dependencies import AuthServices
from rinde.auth.application.unit import AuthUnitFactory
from rinde.auth.domain.errors import AuthError
from rinde.auth.infrastructure.argon2_hasher import Argon2PasswordHasher
from rinde.auth.infrastructure.factory import SqlAlchemyAuthUnitFactory
from rinde.auth.infrastructure.pwned_passwords import PwnedPasswordsChecker
from rinde.auth.infrastructure.system import SecureRandomSecrets
from rinde.budgets.api.errors import budgets_error_handler
from rinde.budgets.api.router import router as budgets_router
from rinde.budgets.application.unit import BudgetsGateways, BudgetsUnitFactory
from rinde.budgets.domain.errors import BudgetError
from rinde.budgets.infrastructure.factory import SqlAlchemyBudgetsUnitFactory
from rinde.budgets.infrastructure.gateways import (
    PreferencesRateTypeReader,
    TransactionsCategoryReader,
    TransactionsSpendingReader,
)
from rinde.budgets.infrastructure.gateways import (
    RatesConverterFactory as BudgetsConverterFactory,
)
from rinde.config import Settings, get_settings
from rinde.dashboard.api.router import router as dashboard_router
from rinde.dashboard.application.ports import Clock
from rinde.dashboard.application.use_cases import DashboardDependencies, GetDashboard
from rinde.dashboard.infrastructure.gateways import (
    PreferencesReferenceReader,
    RatesConverterFactory,
    TransactionsLedgerReader,
)
from rinde.health.api.router import router as health_router
from rinde.health.application.check_readiness import CheckReadiness, DatabaseProbe
from rinde.health.infrastructure.database_probe import SqlAlchemyDatabaseProbe
from rinde.preferences.api.errors import preferences_error_handler
from rinde.preferences.api.router import router as preferences_router
from rinde.preferences.application.unit import PreferencesUnitFactory
from rinde.preferences.domain.errors import PreferencesError
from rinde.preferences.infrastructure.factory import SqlAlchemyPreferencesUnitFactory
from rinde.rates.api.errors import rates_error_handler
from rinde.rates.api.router import router as rates_router
from rinde.rates.application.unit import RatesUnitFactory
from rinde.rates.domain.errors import RateError
from rinde.rates.infrastructure.factory import (
    SqlAlchemyRatesUnitFactory,
    build_history_provider,
    build_rate_provider,
)
from rinde.shared.api.csrf import CsrfRejectedError, csrf_error_handler
from rinde.shared.api.errors import domain_error_handler
from rinde.shared.domain.errors import DomainError
from rinde.shared.infrastructure.clock import SystemClock
from rinde.transactions.api.errors import transactions_error_handler
from rinde.transactions.api.router import router as transactions_router
from rinde.transactions.application.unit import TransactionsUnitFactory
from rinde.transactions.domain.errors import CategoryError, TransactionError, TransferError
from rinde.transactions.infrastructure.accounts_gateway import AccountsApplicationGateway
from rinde.transactions.infrastructure.factory import SqlAlchemyTransactionsUnitFactory

API_PREFIX = "/api"
# El prefijo __Host- obliga a Secure, Path=/ y sin Domain: la cookie no se comparte con nadie.
SECURE_COOKIE_NAME = "__Host-rinde_session"
PLAIN_COOKIE_NAME = "rinde_session"
SECONDS_PER_DAY = 24 * 60 * 60


# Un parámetro por módulo con infraestructura reemplazable: la cantidad crece con
# los módulos, no con la complejidad de la función. Todos son opcionales y por nombre.
def create_app(  # noqa: PLR0913
    settings: Settings | None = None,
    *,
    database_probe: DatabaseProbe | None = None,
    auth_factory: AuthUnitFactory | None = None,
    accounts_factory: AccountsUnitFactory | None = None,
    transactions_factory: TransactionsUnitFactory | None = None,
    rates_factory: RatesUnitFactory | None = None,
    preferences_factory: PreferencesUnitFactory | None = None,
    budgets_factory: BudgetsUnitFactory | None = None,
    dashboard_clock: Clock | None = None,
) -> FastAPI:
    """Crea la aplicación.

    Los parámetros opcionales permiten reemplazar la infraestructura en los tests.
    """
    config = settings or get_settings()
    engine: AsyncEngine | None = None
    http_client: httpx.AsyncClient | None = None

    def shared_http_client() -> httpx.AsyncClient:
        nonlocal http_client
        if http_client is None:
            http_client = httpx.AsyncClient(headers={"User-Agent": f"rinde-api/{version('rinde')}"})
        return http_client

    def shared_engine() -> AsyncEngine:
        nonlocal engine
        if engine is None:
            engine = create_async_engine(config.database_url.get_secret_value(), pool_pre_ping=True)
        return engine

    if database_probe is None:
        database_probe = SqlAlchemyDatabaseProbe(shared_engine())
    if auth_factory is None:
        auth_factory = SqlAlchemyAuthUnitFactory(
            async_sessionmaker(shared_engine(), expire_on_commit=False),
            AuthServices(
                hasher=Argon2PasswordHasher(),
                breaches=PwnedPasswordsChecker(
                    shared_http_client(), base_url=config.pwned_passwords_url
                ),
                clock=SystemClock(),
                secrets=SecureRandomSecrets(),
                session_ttl=timedelta(days=config.session_ttl_days),
            ),
        )

    if accounts_factory is None:
        accounts_factory = SqlAlchemyAccountsUnitFactory(
            async_sessionmaker(shared_engine(), expire_on_commit=False), SystemClock()
        )

    if transactions_factory is None:
        clock = SystemClock()

        def account_gateway(session: AsyncSession) -> AccountsApplicationGateway:
            """Movimientos ve las cuentas por el caso de uso de cuentas, en la misma sesión."""
            return AccountsApplicationGateway(
                GetAccount(
                    AccountsDependencies(
                        accounts=SqlAlchemyAccountRepository(session),
                        transaction=SqlAlchemyTransaction(session),
                        clock=clock,
                    )
                )
            )

        transactions_factory = SqlAlchemyTransactionsUnitFactory(
            async_sessionmaker(shared_engine(), expire_on_commit=False), clock, account_gateway
        )

    if rates_factory is None:
        clock = SystemClock()
        rates_factory = SqlAlchemyRatesUnitFactory(
            async_sessionmaker(shared_engine(), expire_on_commit=False),
            build_rate_provider(
                shared_http_client(),
                clock,
                dolarapi_url=config.dolarapi_url,
                argentinadatos_url=config.argentinadatos_url,
                criptoya_url=config.criptoya_url,
            ),
            build_history_provider(
                shared_http_client(), clock, argentinadatos_url=config.argentinadatos_url
            ),
            clock,
        )

    if preferences_factory is None:
        preferences_factory = SqlAlchemyPreferencesUnitFactory(
            async_sessionmaker(shared_engine(), expire_on_commit=False), SystemClock()
        )

    # El dashboard no tiene infraestructura propia: lee a los otros módulos por
    # su capa de aplicación, con las mismas fábricas que usan sus endpoints.
    dashboard = GetDashboard(
        DashboardDependencies(
            ledger=TransactionsLedgerReader(transactions_factory),
            references=PreferencesReferenceReader(preferences_factory),
            converters=RatesConverterFactory(rates_factory),
            clock=dashboard_clock or SystemClock(),
        )
    )

    budgets_factory = budgets_factory or _sql_budgets(
        async_sessionmaker(shared_engine(), expire_on_commit=False),
        transactions_factory,
        preferences_factory,
        rates_factory,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if http_client is not None:
            await http_client.aclose()
        if engine is not None:
            await engine.dispose()

    # En producción no se publica la documentación interactiva: menos superficie de ataque.
    docs_enabled = not config.is_production
    app = FastAPI(
        title="Rinde API",
        version=version("rinde"),
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json" if docs_enabled else None,
        docs_url=f"{API_PREFIX}/docs" if docs_enabled else None,
        redoc_url=None,
    )
    app.state.version = config.version
    app.state.check_readiness = CheckReadiness(database_probe)
    app.state.auth_factory = auth_factory
    app.state.identify = identify_user
    app.state.accounts_factory = accounts_factory
    app.state.transactions_factory = transactions_factory
    app.state.rates_factory = rates_factory
    app.state.preferences_factory = preferences_factory
    app.state.dashboard = dashboard
    app.state.budgets_factory = budgets_factory
    app.state.session_cookie = SessionCookie(
        name=SECURE_COOKIE_NAME if config.session_cookie_secure else PLAIN_COOKIE_NAME,
        secure=config.session_cookie_secure,
        max_age_seconds=config.session_ttl_days * SECONDS_PER_DAY,
    )
    _register_modules(app)
    return app


def _sql_budgets(
    sessionmaker: async_sessionmaker[AsyncSession],
    transactions: TransactionsUnitFactory,
    preferences: PreferencesUnitFactory,
    rates: RatesUnitFactory,
) -> BudgetsUnitFactory:
    """Presupuestos lee a los otros módulos por su capa de aplicación, con las mismas
    fábricas que usan sus endpoints, como el dashboard.
    """
    return SqlAlchemyBudgetsUnitFactory(
        sessionmaker,
        BudgetsGateways(
            categories=TransactionsCategoryReader(transactions),
            spending=TransactionsSpendingReader(transactions),
            rate_types=PreferencesRateTypeReader(preferences),
            converters=BudgetsConverterFactory(rates),
        ),
        SystemClock(),
    )


def _register_modules(app: FastAPI) -> None:
    """Los manejadores de errores y los routers de cada módulo."""
    # Del más general al más específico: Starlette elige el manejador más cercano
    # en la jerarquía del error, así cada módulo sigue traduciendo los suyos.
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(CsrfRejectedError, csrf_error_handler)
    app.add_exception_handler(AuthError, auth_error_handler)
    app.add_exception_handler(AccountError, accounts_error_handler)
    app.add_exception_handler(TransactionError, transactions_error_handler)
    app.add_exception_handler(CategoryError, transactions_error_handler)
    app.add_exception_handler(TransferError, transactions_error_handler)
    app.add_exception_handler(RateError, rates_error_handler)
    app.add_exception_handler(PreferencesError, preferences_error_handler)
    app.add_exception_handler(BudgetError, budgets_error_handler)
    for router in (
        health_router,
        auth_router,
        accounts_router,
        transactions_router,
        rates_router,
        preferences_router,
        dashboard_router,
        budgets_router,
    ):
        app.include_router(router, prefix=API_PREFIX)
