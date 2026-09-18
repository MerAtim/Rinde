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
from rinde.config import Settings, get_settings
from rinde.health.api.router import router as health_router
from rinde.health.application.check_readiness import CheckReadiness, DatabaseProbe
from rinde.health.infrastructure.database_probe import SqlAlchemyDatabaseProbe
from rinde.shared.api.csrf import CsrfRejectedError, csrf_error_handler
from rinde.shared.api.errors import domain_error_handler
from rinde.shared.domain.errors import DomainError
from rinde.shared.infrastructure.clock import SystemClock
from rinde.transactions.api.errors import transactions_error_handler
from rinde.transactions.api.router import router as transactions_router
from rinde.transactions.application.unit import TransactionsUnitFactory
from rinde.transactions.domain.errors import CategoryError, TransactionError
from rinde.transactions.infrastructure.accounts_gateway import AccountsApplicationGateway
from rinde.transactions.infrastructure.factory import SqlAlchemyTransactionsUnitFactory

API_PREFIX = "/api"
# El prefijo __Host- obliga a Secure, Path=/ y sin Domain: la cookie no se comparte con nadie.
SECURE_COOKIE_NAME = "__Host-rinde_session"
PLAIN_COOKIE_NAME = "rinde_session"
SECONDS_PER_DAY = 24 * 60 * 60


def create_app(
    settings: Settings | None = None,
    *,
    database_probe: DatabaseProbe | None = None,
    auth_factory: AuthUnitFactory | None = None,
    accounts_factory: AccountsUnitFactory | None = None,
    transactions_factory: TransactionsUnitFactory | None = None,
) -> FastAPI:
    """Crea la aplicación.

    Los parámetros opcionales permiten reemplazar la infraestructura en los tests.
    """
    config = settings or get_settings()
    engine: AsyncEngine | None = None
    http_client: httpx.AsyncClient | None = None

    def shared_engine() -> AsyncEngine:
        nonlocal engine
        if engine is None:
            engine = create_async_engine(config.database_url.get_secret_value(), pool_pre_ping=True)
        return engine

    if database_probe is None:
        database_probe = SqlAlchemyDatabaseProbe(shared_engine())
    if auth_factory is None:
        http_client = httpx.AsyncClient(headers={"User-Agent": f"rinde-api/{version('rinde')}"})
        auth_factory = SqlAlchemyAuthUnitFactory(
            async_sessionmaker(shared_engine(), expire_on_commit=False),
            AuthServices(
                hasher=Argon2PasswordHasher(),
                breaches=PwnedPasswordsChecker(http_client, base_url=config.pwned_passwords_url),
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
    app.state.session_cookie = SessionCookie(
        name=SECURE_COOKIE_NAME if config.session_cookie_secure else PLAIN_COOKIE_NAME,
        secure=config.session_cookie_secure,
        max_age_seconds=config.session_ttl_days * SECONDS_PER_DAY,
    )
    # Del más general al más específico: Starlette elige el manejador más cercano
    # en la jerarquía del error, así cada módulo sigue traduciendo los suyos.
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(CsrfRejectedError, csrf_error_handler)
    app.add_exception_handler(AuthError, auth_error_handler)
    app.add_exception_handler(AccountError, accounts_error_handler)
    app.add_exception_handler(TransactionError, transactions_error_handler)
    app.add_exception_handler(CategoryError, transactions_error_handler)
    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(accounts_router, prefix=API_PREFIX)
    app.include_router(transactions_router, prefix=API_PREFIX)
    return app
