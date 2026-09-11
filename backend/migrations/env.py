"""Entorno de Alembic: toma la conexión de la configuración de la aplicación."""

import asyncio
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import rinde.auth.infrastructure.tables  # noqa: F401  (registra las tablas en el MetaData)
from rinde.config import get_settings
from rinde.shared.infrastructure.database import metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Todas las tablas se registran en este MetaData: `alembic check` compara el modelo con la base.
target_metadata = metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(
        get_settings().database_url.get_secret_value(),
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    # psycopg asíncrono no funciona con el loop por defecto de Windows.
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(run_migrations_online(), loop_factory=loop_factory)
