import os

import pytest


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("RINDE_DATABASE_URL")
    if url is None:
        if os.environ.get("CI"):
            pytest.fail("En CI los tests de integración requieren RINDE_DATABASE_URL")
        pytest.skip("RINDE_DATABASE_URL no está definida: se omite el test contra PostgreSQL")
    return url
