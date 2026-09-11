"""Raíz de composición: arma la aplicación y conecta cada puerto con su adaptador."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from rinde.config import Settings, get_settings
from rinde.health.api.router import router as health_router
from rinde.health.application.check_readiness import CheckReadiness, DatabaseProbe
from rinde.health.infrastructure.database_probe import SqlAlchemyDatabaseProbe

API_PREFIX = "/api"


def create_app(
    settings: Settings | None = None,
    *,
    database_probe: DatabaseProbe | None = None,
) -> FastAPI:
    """Crea la aplicación. `database_probe` permite reemplazar la base de datos en tests."""
    settings = settings or get_settings()

    engine: AsyncEngine | None = None
    if database_probe is None:
        engine = create_async_engine(settings.database_url.get_secret_value(), pool_pre_ping=True)
        database_probe = SqlAlchemyDatabaseProbe(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if engine is not None:
            await engine.dispose()

    # En producción no se publica la documentación interactiva: menos superficie de ataque.
    docs_enabled = not settings.is_production
    app = FastAPI(
        title="Rinde API",
        version=version("rinde"),
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json" if docs_enabled else None,
        docs_url=f"{API_PREFIX}/docs" if docs_enabled else None,
        redoc_url=None,
    )
    app.state.version = settings.version
    app.state.check_readiness = CheckReadiness(database_probe)
    app.include_router(health_router, prefix=API_PREFIX)
    return app
