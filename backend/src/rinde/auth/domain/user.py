"""Cuenta de usuario. Solo guarda lo necesario para autenticar: ningún dato personal."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from rinde.auth.domain.username import Username


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    username: Username
    password_hash: str
    recovery_code_hash: str
    created_at: datetime
