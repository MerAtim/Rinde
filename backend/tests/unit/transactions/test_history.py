"""El historial unificado: movimientos y transferencias en una sola lista (ADR-0014)."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from rinde.shared.domain.money import Currency
from rinde.transactions.application.ports import TransactionFilters
from rinde.transactions.application.use_cases import TransactionInput, TransferInput
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.transfer import Transfer
from tests.unit.transactions.fakes import Harness

pytestmark = pytest.mark.anyio

DUENO = uuid4()
OTRA_PERSONA = uuid4()


@pytest.fixture
def harness() -> Harness:
    return Harness()


@pytest.fixture
def banco(harness: Harness) -> UUID:
    account_id = uuid4()
    harness.accounts.add(account_id, DUENO, Currency.ARS)
    return account_id


@pytest.fixture
def efectivo(harness: Harness) -> UUID:
    account_id = uuid4()
    harness.accounts.add(account_id, DUENO, Currency.ARS)
    return account_id


def _categoria(harness: Harness) -> Category:
    categoria = Category(
        id=uuid4(),
        owner_id=DUENO,
        name=CategoryName.parse("Supermercado"),
        kind=TransactionKind.EXPENSE,
        created_at=harness.clock.now(),
    )
    harness.categories.rows[categoria.id] = categoria
    return categoria


async def _gasto(harness: Harness, cuenta: UUID, dia: int) -> UUID:
    categoria = _categoria(harness)
    movimiento = await harness.unit.register.execute(
        DUENO,
        TransactionInput(
            account_id=cuenta,
            kind=TransactionKind.EXPENSE,
            amount=Decimal("100.00"),
            category_id=categoria.id,
            occurred_on=date(2026, 9, dia),
        ),
    )
    return movimiento.id


async def _transferencia(harness: Harness, origen: UUID, destino: UUID, dia: int) -> UUID:
    transferencia = await harness.unit.register_transfer.execute(
        DUENO,
        TransferInput(
            from_account_id=origen,
            to_account_id=destino,
            sent=Decimal("500.00"),
            received=Decimal("500.00"),
            occurred_on=date(2026, 9, dia),
        ),
    )
    return transferencia.id


class TestIntercalar:
    async def test_mezcla_las_dos_fuentes_de_la_mas_nueva_a_la_mas_vieja(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        viejo = await _gasto(harness, banco, 10)
        medio = await _transferencia(harness, banco, efectivo, 11)
        nuevo = await _gasto(harness, banco, 12)

        pagina = await harness.unit.history.execute(DUENO, TransactionFilters())

        assert [item.id for item in pagina.items] == [nuevo, medio, viejo]

    async def test_distingue_un_movimiento_de_una_transferencia(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        await _gasto(harness, banco, 10)
        await _transferencia(harness, banco, efectivo, 11)

        pagina = await harness.unit.history.execute(DUENO, TransactionFilters())

        clases = [isinstance(item, Transfer) for item in pagina.items]
        assert clases == [True, False]

    async def test_no_devuelve_lo_de_otra_persona(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        await _gasto(harness, banco, 10)
        await _transferencia(harness, banco, efectivo, 11)

        pagina = await harness.unit.history.execute(OTRA_PERSONA, TransactionFilters())

        assert pagina.items == []

    async def test_lo_borrado_no_aparece(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        transferencia = await _transferencia(harness, banco, efectivo, 11)
        movimiento = await _gasto(harness, banco, 10)
        await harness.unit.delete_transfer.execute(DUENO, transferencia)

        pagina = await harness.unit.history.execute(DUENO, TransactionFilters())

        assert [item.id for item in pagina.items] == [movimiento]

    async def test_la_cuenta_filtra_las_dos_fuentes(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        ajena = uuid4()
        harness.accounts.add(ajena, DUENO, Currency.ARS)
        en_banco = await _gasto(harness, banco, 12)
        transferencia = await _transferencia(harness, banco, efectivo, 11)
        await _gasto(harness, efectivo, 10)

        pagina = await harness.unit.history.execute(DUENO, TransactionFilters(account_id=banco))

        assert [item.id for item in pagina.items] == [en_banco, transferencia]


class TestPaginar:
    async def test_recorre_todo_sin_repetir_ni_saltear(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        """El caso que importa: dos fuentes intercaladas y páginas chicas."""
        esperados: list[UUID] = []
        for dia in range(10, 16):
            # Un movimiento y una transferencia por día: las dos ramas siempre
            # tienen algo para aportar, que es cuando la mezcla puede fallar.
            esperados.append(await _gasto(harness, banco, dia))
            esperados.append(await _transferencia(harness, banco, efectivo, dia))

        vistos: list[UUID] = []
        cursor: str | None = None
        for _ in range(20):
            pagina = await harness.unit.history.execute(
                DUENO, TransactionFilters(), cursor=cursor, limit=3
            )
            assert len(pagina.items) <= 3
            vistos.extend(item.id for item in pagina.items)
            cursor = pagina.next_cursor
            if cursor is None:
                break

        assert cursor is None, "la paginación no terminó"
        assert len(vistos) == len(set(vistos)), "hay filas repetidas"
        assert set(vistos) == set(esperados), "faltan filas"
        assert len(vistos) == 12

    async def test_la_ultima_pagina_no_ofrece_continuacion(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        await _gasto(harness, banco, 10)
        await _transferencia(harness, banco, efectivo, 11)

        pagina = await harness.unit.history.execute(DUENO, TransactionFilters(), limit=50)

        assert pagina.next_cursor is None

    async def test_ofrece_continuacion_aunque_entren_justas(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        """Dos filas y un límite de dos: la rama de movimientos todavía tiene más."""
        await _gasto(harness, banco, 10)
        await _gasto(harness, banco, 11)
        await _gasto(harness, banco, 12)

        primera = await harness.unit.history.execute(DUENO, TransactionFilters(), limit=2)
        assert primera.next_cursor is not None

        segunda = await harness.unit.history.execute(
            DUENO, TransactionFilters(), cursor=primera.next_cursor, limit=2
        )
        assert len(segunda.items) == 1
        assert segunda.next_cursor is None

    async def test_sin_nada_no_ofrece_continuacion(self, harness: Harness) -> None:
        pagina = await harness.unit.history.execute(DUENO, TransactionFilters())

        assert pagina.items == []
        assert pagina.next_cursor is None
