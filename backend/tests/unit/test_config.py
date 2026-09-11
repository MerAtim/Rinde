import pytest
from pydantic import SecretStr, ValidationError

from rinde.config import Settings, get_settings

SECRET_URL = "postgresql+psycopg://rinde:super-secreta@localhost:5432/rinde"


def test_rejects_database_url_without_psycopg_driver() -> None:
    with pytest.raises(ValidationError, match="postgresql\\+psycopg://"):
        Settings(database_url=SecretStr("postgresql://rinde@localhost/rinde"))


def test_database_url_never_appears_in_repr() -> None:
    settings = Settings(database_url=SecretStr(SECRET_URL))

    assert "super-secreta" not in repr(settings)
    assert "super-secreta" not in str(settings.model_dump())


def test_reads_configuration_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RINDE_DATABASE_URL", SECRET_URL)
    monkeypatch.setenv("RINDE_ENVIRONMENT", "production")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url.get_secret_value() == SECRET_URL
    assert settings.is_production
    get_settings.cache_clear()
