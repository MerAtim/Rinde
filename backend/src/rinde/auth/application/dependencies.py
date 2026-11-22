"""Dependencias de los casos de uso: servicios compartidos y repositorios de un pedido."""

from dataclasses import dataclass
from datetime import timedelta

from rinde.auth.application.ports import (
    BreachedPasswordChecker,
    ClientActivityRepository,
    Clock,
    DemoSeeder,
    FailedAttemptRepository,
    PasswordHasher,
    SecretGenerator,
    SecurityLog,
    SessionRepository,
    Transaction,
    UserRepository,
)


@dataclass(frozen=True, slots=True)
class AuthServices:
    """Servicios sin estado, compartidos por todos los pedidos."""

    hasher: PasswordHasher
    breaches: BreachedPasswordChecker
    clock: Clock
    secrets: SecretGenerator
    session_ttl: timedelta
    demo_seeder: DemoSeeder
    security_log: SecurityLog


@dataclass(frozen=True, slots=True)
class AuthDependencies:
    """Repositorios de un pedido, que comparten una misma transacción."""

    users: UserRepository
    sessions: SessionRepository
    failed_attempts: FailedAttemptRepository
    client_activity: ClientActivityRepository
    transaction: Transaction
    services: AuthServices
