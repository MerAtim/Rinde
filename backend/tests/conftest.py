import asyncio
import os
import sys

import pytest
from hypothesis import settings as hypothesis_settings
from pydantic import SecretStr

from rinde.config import Settings

# En CI los casos generados son siempre los mismos: un test que falla tiene que
# fallar igual al reintentarlo. En local se exploran casos nuevos en cada corrida.
hypothesis_settings.register_profile("ci", derandomize=True, max_examples=200)
if os.environ.get("CI"):
    hypothesis_settings.load_profile("ci")


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
