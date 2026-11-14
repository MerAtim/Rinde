"""Caso de uso del dashboard (ADR-0018)."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from rinde.dashboard.application.ports import (
    Clock,
    ConverterFactory,
    LedgerReader,
    PriceIndexReader,
    Reference,
    ReferenceReader,
    SameCurrencyConverter,
)
from rinde.dashboard.domain.errors import DashboardConstantPricesArsOnlyError
from rinde.dashboard.domain.period import Period
from rinde.dashboard.domain.report import Converter, PriceIndex, Report, build_report
from rinde.shared.domain.calendar import argentine_day
from rinde.shared.domain.money import Currency


@dataclass(frozen=True, slots=True)
class DashboardDependencies:
    ledger: LedgerReader
    references: ReferenceReader
    converters: ConverterFactory
    prices: PriceIndexReader
    clock: Clock


@dataclass(frozen=True, slots=True)
class Dashboard:
    period: Period
    reference: Reference
    report: Report


class GetDashboard:
    """El dashboard de una persona para un período y, si elige, algunas cuentas."""

    def __init__(self, deps: DashboardDependencies) -> None:
        self._deps = deps

    async def execute(
        self,
        owner_id: UUID,
        *,
        first: date | None = None,
        last: date | None = None,
        account_ids: frozenset[UUID] | None = None,
        constant_prices: bool = False,
    ) -> Dashboard:
        """Con `constant_prices`, además, el flujo mensual en pesos de hoy (ADR-0025)."""
        period = Period.of(first, last, argentine_day(self._deps.clock.now()))
        # La referencia va primero: dice qué hace falta pedir por día.
        reference = await self._deps.references.reference(owner_id)
        # Antes de leer nada: el IPC solo mide precios en pesos.
        if constant_prices and reference.currency is not Currency.ARS:
            raise DashboardConstantPricesArsOnlyError
        ledger = await self._deps.ledger.ledger(
            owner_id, period.since, period.until, account_ids, reference.currency
        )
        currencies = {flow.money.currency for flow in ledger.flows} | {
            change.change.currency for change in ledger.balance_changes
        }
        converter: Converter = SameCurrencyConverter(reference.currency)
        # Solo se buscan cotizaciones si hay algo en otra moneda: quien tiene
        # todo en pesos no espera a ninguna fuente.
        if currencies - {reference.currency}:
            converter = await self._deps.converters.converter(
                reference.currency, reference.rate_type, period.since, period.until
            )
        prices: PriceIndex | None = None
        # El IPC se consulta solo si se pidió: el dashboard de siempre no cambia.
        if constant_prices:
            prices = await self._deps.prices.index(period.since, period.until)
        return Dashboard(
            period=period,
            reference=reference,
            report=build_report(period, ledger.flows, ledger.balance_changes, converter, prices),
        )
