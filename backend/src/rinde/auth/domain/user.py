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
    demo_expires_at: datetime | None = None
    """Solo en una cuenta demo: cuándo vence y se borra (ADR-0028)."""

    @property
    def is_demo(self) -> bool:
        return self.demo_expires_at is not None

    def is_expired(self, now: datetime) -> bool:
        return self.demo_expires_at is not None and self.demo_expires_at <= now
