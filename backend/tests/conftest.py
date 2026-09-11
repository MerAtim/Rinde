import asyncio
import sys

import pytest
from pydantic import SecretStr

from rinde.config import Settings


@pytest.fixture
def anyio_backend() -> tuple[str, dict[str, object]]:
    """asyncio en todas las plataformas; en Windows, con el loop que exige psycopg."""
    if sys.platform == "win32":
        return "asyncio", {"loop_factory": asyncio.SelectorEventLoop}
    return "asyncio", {}


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        database_url=SecretStr("postgresql+psycopg://test:test@localhost:5432/test"),
    )
