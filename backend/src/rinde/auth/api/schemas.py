"""Esquemas de entrada y salida.

La política real vive en el dominio: acá solo se acota el tamaño de la entrada.
"""

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=512)


class RecoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    recovery_code: SecretStr = Field(min_length=1, max_length=64)
    new_password: SecretStr = Field(min_length=1, max_length=512)


class RegisterResponse(BaseModel):
    username: str
    recovery_code: str


class RecoverResponse(BaseModel):
    recovery_code: str


class MeResponse(BaseModel):
    username: str
