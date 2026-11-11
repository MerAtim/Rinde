"""Adaptadores hacia los otros módulos: el dashboard los lee por su capa de aplicación.

Cada adaptador abre su propia unidad de trabajo, con su sesión, y la cierra al
terminar. Son solo lecturas: ninguna confirma nada, salvo cotizaciones, que
guarda los días de la serie que le faltaban (ADR-0018).
"""

from datetime import date
from uuid import UUID

from rinde.dashboard.application.ports import Ledger, Reference
from rinde.dashboard.domain.report import (
    BalanceChange,
    CategoryRef,
    Converter,
    Flow,
    FlowKind,
)
from rinde.preferences.application.unit import PreferencesUnitFactory
from rinde.rates.application.unit import RatesUnitFactory
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType
from rinde.transactions.application.ports import LedgerScope
from rinde.transactions.application.unit import TransactionsUnitFactory


class TransactionsLedgerReader:
    def __init__(self, factory: TransactionsUnitFactory) -> None:
        self._factory = factory

    async def ledger(
        self,
        owner_id: UUID,
        since: date,
        until: date,
        account_ids: frozenset[UUID] | None,
        reference: Currency,
    ) -> Ledger:
        scope = LedgerScope(
            since=since, until=until, account_ids=account_ids, monthly_currency=reference
        )
        async with self._factory() as unit:
            summary = await unit.summary.execute(owner_id, scope)
        return Ledger(
            flows=[
                Flow(
                    day=flow.day,
                    kind=FlowKind(flow.kind.value),
                    category=CategoryRef(
                        id=flow.category_id, name=flow.category_name, slug=flow.category_slug
                    ),
                    money=flow.total,
                )
                for flow in summary.flows
            ],
            balance_changes=[
                BalanceChange(
                    account_id=change.account_id, month=change.month, change=change.change
                )
                for change in summary.balance_changes
            ],
        )


class PreferencesReferenceReader:
    def __init__(self, factory: PreferencesUnitFactory) -> None:
        self._factory = factory

    async def reference(self, owner_id: UUID) -> Reference:
        async with self._factory() as unit:
            preferences = await unit.get.execute(owner_id)
        return Reference(currency=preferences.reference_currency, rate_type=preferences.rate_type)


class RatesConverterFactory:
    def __init__(self, factory: RatesUnitFactory) -> None:
        self._factory = factory

    async def converter(
        self, target: Currency, rate_type: RateType, since: date, until: date
    ) -> Converter:
        async with self._factory() as unit:
            # `DayConverter` ya cumple el puerto del dashboard: no hace falta traducirlo.
            return await unit.converter.execute(target, rate_type, since, until)
