"""Configuración de la aplicación, leída de variables de entorno con prefijo RINDE_."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DATABASE_DRIVER = "postgresql+psycopg://"
_MIN_ORIGIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Parámetros de ejecución. Los secretos son SecretStr: nunca aparecen en logs ni en repr."""

    model_config = SettingsConfigDict(env_prefix="RINDE_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    # Commit desplegado; lo fija la imagen de producción. Permite verificar qué versión corre.
    version: str = "dev"
    # Sesiones (ADR-0007). La cookie lleva Secure salvo en Docker local por HTTP.
    session_ttl_days: int = Field(default=30, ge=1, le=90)
    session_cookie_secure: bool = True
    pwned_passwords_url: str = "https://api.pwnedpasswords.com/range/"
    # Fuentes de cotizaciones (ADR-0016). Configurables para apuntarlas a un doble en pruebas.
    dolarapi_url: str = "https://dolarapi.com"
    argentinadatos_url: str = "https://api.argentinadatos.com"
    criptoya_url: str = "https://criptoya.com"
    # Precio del Bitcoin (ADR-0029).
    kraken_url: str = "https://api.kraken.com"
    bitstamp_url: str = "https://www.bitstamp.net"
    # IPC del INDEC para los pesos constantes (ADR-0025).
    datos_gob_ar_url: str = "https://apis.datos.gob.ar"
    # Secreto que manda el Worker de Cloudflare (ADR-0032). Varios separados por
    # coma, para rotarlo sin corte. Obligatorio en producción.
    origin_secret: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def _require_psycopg_driver(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(_DATABASE_DRIVER):
            msg = f"RINDE_DATABASE_URL debe usar el driver {_DATABASE_DRIVER}"
            raise ValueError(msg)
        return value

    @field_validator("origin_secret")
    @classmethod
    def _require_strong_origin_secrets(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and any(
            len(secret) < _MIN_ORIGIN_SECRET_LENGTH for secret in _split(value)
        ):
            msg = (
                "Cada secreto de RINDE_ORIGIN_SECRET necesita "
                f"{_MIN_ORIGIN_SECRET_LENGTH} caracteres o más"
            )
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _require_origin_secret_in_production(self) -> Self:
        # Seguro por defecto: sin el secreto, la API de producción quedaría
        # abierta a quien la llame directo, así que no arranca.
        if self.is_production and self.origin_secret is None:
            msg = "En producción hace falta RINDE_ORIGIN_SECRET (ADR-0032)"
            raise ValueError(msg)
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def origin_secrets(self) -> tuple[str, ...]:
        return _split(self.origin_secret) if self.origin_secret is not None else ()


def _split(value: SecretStr) -> tuple[str, ...]:
    return tuple(secret.strip() for secret in value.get_secret_value().split(","))


@lru_cache
def get_settings() -> Settings:
    """Configuración única del proceso, tomada del entorno."""
    return Settings()
