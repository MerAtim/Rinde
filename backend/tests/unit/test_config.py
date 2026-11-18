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


ORIGIN_SECRET = "s" * 32


def test_reads_configuration_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RINDE_DATABASE_URL", SECRET_URL)
    monkeypatch.setenv("RINDE_ENVIRONMENT", "production")
    monkeypatch.setenv("RINDE_ORIGIN_SECRET", ORIGIN_SECRET)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url.get_secret_value() == SECRET_URL
    assert settings.is_production
    get_settings.cache_clear()


def test_version_defaults_to_dev_and_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings(database_url=SecretStr(SECRET_URL)).version == "dev"

    monkeypatch.setenv("RINDE_VERSION", "abc123")

    assert Settings(database_url=SecretStr(SECRET_URL)).version == "abc123"


def test_production_does_not_start_without_origin_secret() -> None:
    with pytest.raises(ValidationError, match="RINDE_ORIGIN_SECRET"):
        Settings(database_url=SecretStr(SECRET_URL), environment="production")


def test_an_origin_secret_shorter_than_32_characters_is_rejected() -> None:
    with pytest.raises(ValidationError, match="32 caracteres"):
        Settings(
            database_url=SecretStr(SECRET_URL), origin_secret=SecretStr(f"{ORIGIN_SECRET},corto")
        )


def test_several_origin_secrets_separated_by_comma_for_rotation() -> None:
    settings = Settings(
        database_url=SecretStr(SECRET_URL), origin_secret=SecretStr(f"{ORIGIN_SECRET}, {'t' * 32}")
    )

    assert settings.origin_secrets == (ORIGIN_SECRET, "t" * 32)
    assert ORIGIN_SECRET not in repr(settings)
