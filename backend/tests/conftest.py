import asyncio
import json
import logging
import os
import sys
from collections.abc import Callable, Iterator
from io import StringIO
from typing import Any

import pytest
from hypothesis import settings as hypothesis_settings
from pydantic import SecretStr

from rinde.config import Settings
from rinde.shared.infrastructure.security_log import LOGGER_NAME, SecurityEventFormatter

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


@pytest.fixture
def security_events() -> Iterator[Callable[[], list[dict[str, Any]]]]:
    """Las líneas que escribe el registro de seguridad, ya leídas como JSON.

    Usa el mismo formato que producción, así el test ve exactamente lo que
    quedaría guardado en Render.
    """
    logger = logging.getLogger(LOGGER_NAME)
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SecurityEventFormatter())
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    def read() -> list[dict[str, Any]]:
        return [json.loads(line) for line in stream.getvalue().splitlines()]

    yield read
    logger.removeHandler(handler)
    logger.setLevel(previous_level)
