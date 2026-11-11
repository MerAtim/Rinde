"""Puertos del dashboard: lo que necesita de los otros módulos, dicho en sus términos.

El dashboard no tiene tablas propias. Lee a los otros módulos por su capa de
aplicación, con adaptadores que la raíz de composición arma (ADR-0001).
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from rinde.dashboard.domain.report import BalanceChange, Converter, Flow
from rinde.shared.domain.money import Currency, Money
from rinde.shared.domain.rate_type import RateType


@dataclass(frozen=True, slots=True)
class Ledger:
    flows: list[Flow]
    balance_changes: list[BalanceChange]


@dataclass(frozen=True, slots=True)
class Reference:
    """En qué moneda se muestran los totales y con qué dólar se convierte (ADR-0017)."""

    currency: Currency
    rate_type: RateType


class LedgerReader(Protocol):
    async def ledger(
        self,
        owner_id: UUID,
        since: date,
        until: date,
        account_ids: frozenset[UUID] | None,
        reference: Currency,
    ) -> Ledger:
        """Solo lo del dueño: una cuenta ajena en `account_ids` no agrega nada.

        Los flujos en la moneda de referencia pueden venir sumados por mes, con
        `day` en el primer día: no se convierten, así que el día no hace falta.
        """
        ...


class ReferenceReader(Protocol):
    async def reference(self, owner_id: UUID) -> Reference: ...


class ConverterFactory(Protocol):
    async def converter(
        self, target: Currency, rate_type: RateType, since: date, until: date
    ) -> Converter:
        """Con la cotización de cada día del rango ya traída: convertir no consulta nada."""
        ...


class SameCurrencyConverter:
    """Cuando todo ya está en la moneda de destino no hace falta ninguna cotización."""

    def __init__(self, target: Currency) -> None:
        self._target = target

    @property
    def target(self) -> Currency:
        return self._target

    def supports(self, currency: Currency) -> bool:
        return currency is self._target

    def to_target(self, money: Money, day: date) -> Decimal | None:
        return money.amount if money.currency is self._target else None


class Clock(Protocol):
    def now(self) -> datetime: ...
