"""Configuración de la aplicación, leída de variables de entorno con prefijo RINDE_."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DATABASE_DRIVER = "postgresql+psycopg://"


class Settings(BaseSettings):
    """Parámetros de ejecución. Los secretos son SecretStr: nunca aparecen en logs ni en repr."""

    model_config = SettingsConfigDict(env_prefix="RINDE_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr

    @field_validator("database_url")
    @classmethod
    def _require_psycopg_driver(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(_DATABASE_DRIVER):
            msg = f"RINDE_DATABASE_URL debe usar el driver {_DATABASE_DRIVER}"
            raise ValueError(msg)
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Configuración única del proceso, tomada del entorno."""
    return Settings()
