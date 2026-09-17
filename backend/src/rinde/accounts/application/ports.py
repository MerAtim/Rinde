"""Puertos del módulo de cuentas.

El repositorio no ofrece buscar una cuenta solo por su identificador: toda
lectura pide también el dueño. Así un caso de uso no puede olvidarse de filtrar
por el usuario autenticado, porque no tiene otra forma de pedirla (ADR-0009).
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from rinde.accounts.domain.account import Account


class AccountRepository(Protocol):
    async def add(self, account: Account) -> None: ...

    async def get(self, account_id: UUID, owner_id: UUID) -> Account | None: ...

    async def list_for_owner(self, owner_id: UUID, *, include_archived: bool) -> list[Account]:
        """Ordenadas por fecha de creación, las más viejas primero."""
        ...

    async def save(self, account: Account) -> None: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...
