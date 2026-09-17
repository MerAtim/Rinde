"""Reloj del sistema, siempre en UTC. Lo usan todos los módulos."""

from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
