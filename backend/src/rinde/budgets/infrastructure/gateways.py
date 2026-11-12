"""Adaptadores hacia los otros módulos: presupuestos los lee por su capa de aplicación.

Cada adaptador abre su propia unidad de trabajo y la cierra al terminar. Son
solo lecturas, salvo dos efectos que ya tienen esos casos de uso: la primera
lista de categorías siembra las de siempre (ADR-0011), y cotizaciones guarda
los días de la serie que le faltaban (ADR-0018).
"""

from datetime import date
from uuid import UUID

from rinde.budgets.application.ports import CategoryExpense, CategoryInfo
from rinde.budgets.domain.budget import Converter
from rinde.preferences.application.unit import PreferencesUnitFactory
from rinde.rates.application.unit import RatesUnitFactory
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType
from rinde.transactions.application.ports import LedgerScope
from rinde.transactions.application.unit import TransactionsUnitFactory

# El tipo se compara por su valor: el dominio de movimientos no se importa directo.
EXPENSE = "expense"


class TransactionsCategoryReader:
    def __init__(self, factory: TransactionsUnitFactory) -> None:
        self._factory = factory

    async def categories(self, owner_id: UUID) -> list[CategoryInfo]:
        async with self._factory() as unit:
            categories = await unit.categories.execute(owner_id)
        return [
            CategoryInfo(
                id=category.id,
                name=category.name.value,
                slug=category.slug,
                is_expense=category.kind.value == EXPENSE,
            )
            for category in categories
        ]


class TransactionsSpendingReader:
    def __init__(self, factory: TransactionsUnitFactory) -> None:
        self._factory = factory

    async def expenses(self, owner_id: UUID, since: date, until: date) -> list[CategoryExpense]:
        async with self._factory() as unit:
            summary = await unit.summary.execute(owner_id, LedgerScope(since=since, until=until))
        return [
            CategoryExpense(category_id=flow.category_id, day=flow.day, money=flow.total)
            for flow in summary.flows
            if flow.kind.value == EXPENSE
        ]


class PreferencesRateTypeReader:
    def __init__(self, factory: PreferencesUnitFactory) -> None:
        self._factory = factory

    async def rate_type(self, owner_id: UUID) -> RateType:
        async with self._factory() as unit:
            preferences = await unit.get.execute(owner_id)
        return preferences.rate_type


class RatesConverterFactory:
    def __init__(self, factory: RatesUnitFactory) -> None:
        self._factory = factory

    async def converter(
        self, target: Currency, rate_type: RateType, since: date, until: date
    ) -> Converter:
        async with self._factory() as unit:
            # `DayConverter` ya cumple el puerto: no hace falta traducirlo.
            return await unit.converter.execute(target, rate_type, since, until)
