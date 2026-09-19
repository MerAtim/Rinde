"""Casos de uso de transferencias, sobre puertos en memoria (ADR-0014)."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from rinde.shared.domain.money import Currency, Money
from rinde.transactions.application.ports import (
    IdempotentResource,
    RememberedKey,
    TransactionFilters,
    TransferFilters,
)
from rinde.transactions.application.use_cases import TransactionInput, TransferInput
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.errors import (
    IdempotencyKeyReusedError,
    TransactionAccountArchivedError,
    TransactionAccountNotFoundError,
    TransferNotFoundError,
    TransferSameAccountError,
)
from rinde.transactions.domain.transaction import AuditAction
from tests.unit.transactions.fakes import Harness, a_date

pytestmark = pytest.mark.anyio

DUENO = uuid4()
OTRA_PERSONA = uuid4()


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


@pytest.fixture
def dolares(harness: Harness) -> UUID:
    account_id = uuid4()
    harness.accounts.add(account_id, DUENO, Currency.USD)
    return account_id


@pytest.fixture
def harness() -> Harness:
    return Harness()


def un_pedido(origen: UUID, destino: UUID, **cambios: object) -> TransferInput:
    valores: dict[str, object] = {
        "from_account_id": origen,
        "to_account_id": destino,
        "sent": Decimal("50000.00"),
        "received": Decimal("50000.00"),
        "occurred_on": a_date(),
        "description": None,
    }
    valores.update(cambios)
    return TransferInput(**valores)  # type: ignore[arg-type]


def pesos(monto: str) -> Money:
    return Money(Decimal(monto), Currency.ARS)


class TestRegistrar:
    async def test_mueve_el_saldo_de_una_cuenta_a_la_otra(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        await harness.unit.register_transfer.execute(DUENO, un_pedido(banco, efectivo))

        saldos = {b.account_id: b.balance for b in await harness.unit.balances.execute(DUENO)}
        assert saldos[banco] == pesos("-50000.00")
        assert saldos[efectivo] == pesos("50000.00")

    async def test_el_saldo_suma_movimientos_y_transferencias(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        """El costo de que la transferencia sea una entidad propia: dos fuentes, un saldo."""
        categoria = _una_categoria(harness)
        await harness.unit.register.execute(
            DUENO,
            _ingreso(banco, categoria.id, Decimal("100000.00")),
        )
        await harness.unit.register_transfer.execute(
            DUENO,
            un_pedido(banco, efectivo, sent=Decimal("30000.00"), received=Decimal("30000.00")),
        )

        saldos = {b.account_id: b.balance for b in await harness.unit.balances.execute(DUENO)}
        assert saldos[banco] == pesos("70000.00")
        assert saldos[efectivo] == pesos("30000.00")

    async def test_no_aparece_en_la_lista_de_movimientos(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        """La razón de ser del modelo: un reporte de gastos no la puede ver."""
        await harness.unit.register_transfer.execute(DUENO, un_pedido(banco, efectivo))

        pagina = await harness.unit.list.execute(DUENO, TransactionFilters())
        assert pagina.items == []

    async def test_entre_monedas_distintas_guarda_los_dos_montos(
        self, harness: Harness, banco: UUID, dolares: UUID
    ) -> None:
        pedido = un_pedido(banco, dolares, sent=Decimal("100000.00"), received=Decimal("80.00"))

        transferencia = await harness.unit.register_transfer.execute(DUENO, pedido)

        assert transferencia.sent == pesos("100000.00")
        assert transferencia.received == Money(Decimal("80.00"), Currency.USD)

    async def test_queda_registrada_en_la_auditoria(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        await harness.unit.register_transfer.execute(DUENO, un_pedido(banco, efectivo))

        assert harness.transfer_audit.actions == [AuditAction.REGISTERED]

    async def test_confirma_la_transaccion_de_base(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        await harness.unit.register_transfer.execute(DUENO, un_pedido(banco, efectivo))

        assert harness.db.commits == 1


class TestReglasAlRegistrar:
    async def test_rechaza_la_misma_cuenta_de_origen_y_destino(
        self, harness: Harness, banco: UUID
    ) -> None:
        with pytest.raises(TransferSameAccountError):
            await harness.unit.register_transfer.execute(DUENO, un_pedido(banco, banco))

    async def test_una_cuenta_ajena_se_informa_como_inexistente(
        self, harness: Harness, banco: UUID
    ) -> None:
        ajena = uuid4()
        harness.accounts.add(ajena, OTRA_PERSONA, Currency.ARS)

        with pytest.raises(TransactionAccountNotFoundError):
            await harness.unit.register_transfer.execute(DUENO, un_pedido(banco, ajena))

    async def test_no_se_transfiere_a_una_cuenta_archivada(
        self, harness: Harness, banco: UUID
    ) -> None:
        archivada = uuid4()
        harness.accounts.add(archivada, DUENO, Currency.ARS, archived=True)

        with pytest.raises(TransactionAccountArchivedError):
            await harness.unit.register_transfer.execute(DUENO, un_pedido(banco, archivada))

    async def test_no_se_transfiere_desde_una_cuenta_archivada(
        self, harness: Harness, efectivo: UUID
    ) -> None:
        archivada = uuid4()
        harness.accounts.add(archivada, DUENO, Currency.ARS, archived=True)

        with pytest.raises(TransactionAccountArchivedError):
            await harness.unit.register_transfer.execute(DUENO, un_pedido(archivada, efectivo))


class TestIdempotencia:
    async def test_el_mismo_pedido_con_la_misma_clave_no_duplica(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        pedido = un_pedido(banco, efectivo)

        primera = await harness.unit.register_transfer.execute(DUENO, pedido, "clave-1")
        segunda = await harness.unit.register_transfer.execute(DUENO, pedido, "clave-1")

        assert primera.id == segunda.id
        assert len(harness.transfers.rows) == 1

    async def test_la_misma_clave_con_otro_pedido_es_un_error_de_quien_llama(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        await harness.unit.register_transfer.execute(DUENO, un_pedido(banco, efectivo), "clave-1")

        otro = un_pedido(banco, efectivo, sent=Decimal("999.00"), received=Decimal("999.00"))
        with pytest.raises(IdempotencyKeyReusedError):
            await harness.unit.register_transfer.execute(DUENO, otro, "clave-1")

    async def test_una_clave_usada_por_un_movimiento_no_sirve_para_una_transferencia(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        """El discriminador existe para que esto falle sin depender de la huella."""
        await harness.idempotency.remember(
            DUENO,
            "clave-1",
            RememberedKey("otra-huella", IdempotentResource.TRANSACTION, uuid4()),
            harness.clock.now(),
        )

        with pytest.raises(IdempotencyKeyReusedError):
            await harness.unit.register_transfer.execute(
                DUENO, un_pedido(banco, efectivo), "clave-1"
            )


class TestEditar:
    async def test_corrige_las_cuentas_elegidas(
        self, harness: Harness, banco: UUID, efectivo: UUID, dolares: UUID
    ) -> None:
        """Equivocarse de cuenta es el error más fácil al cargar una transferencia."""
        transferencia = await harness.unit.register_transfer.execute(
            DUENO, un_pedido(banco, efectivo)
        )

        corregida = await harness.unit.edit_transfer.execute(
            DUENO,
            transferencia.id,
            un_pedido(banco, dolares, sent=Decimal("50000.00"), received=Decimal("40.00")),
        )

        assert corregida.to_account_id == dolares
        assert corregida.received == Money(Decimal("40.00"), Currency.USD)
        assert harness.transfer_audit.actions == [AuditAction.REGISTERED, AuditAction.EDITED]

    async def test_una_transferencia_ajena_no_se_edita(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        transferencia = await harness.unit.register_transfer.execute(
            DUENO, un_pedido(banco, efectivo)
        )

        with pytest.raises(TransferNotFoundError):
            await harness.unit.edit_transfer.execute(
                OTRA_PERSONA, transferencia.id, un_pedido(banco, efectivo)
            )


class TestBorrarYDeshacer:
    async def test_borrar_saca_la_transferencia_del_saldo(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        transferencia = await harness.unit.register_transfer.execute(
            DUENO, un_pedido(banco, efectivo)
        )

        await harness.unit.delete_transfer.execute(DUENO, transferencia.id)

        assert await harness.unit.balances.execute(DUENO) == []

    async def test_deshacer_la_devuelve_al_saldo(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        transferencia = await harness.unit.register_transfer.execute(
            DUENO, un_pedido(banco, efectivo)
        )
        await harness.unit.delete_transfer.execute(DUENO, transferencia.id)

        await harness.unit.restore_transfer.execute(DUENO, transferencia.id)

        saldos = {b.account_id: b.balance for b in await harness.unit.balances.execute(DUENO)}
        assert saldos[efectivo] == pesos("50000.00")

    async def test_una_transferencia_borrada_no_se_puede_consultar(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        transferencia = await harness.unit.register_transfer.execute(
            DUENO, un_pedido(banco, efectivo)
        )
        await harness.unit.delete_transfer.execute(DUENO, transferencia.id)

        with pytest.raises(TransferNotFoundError):
            await harness.unit.get_transfer.execute(DUENO, transferencia.id)

    async def test_una_transferencia_ajena_no_se_borra(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        transferencia = await harness.unit.register_transfer.execute(
            DUENO, un_pedido(banco, efectivo)
        )

        with pytest.raises(TransferNotFoundError):
            await harness.unit.delete_transfer.execute(OTRA_PERSONA, transferencia.id)


class TestListar:
    async def test_la_cuenta_filtra_de_los_dos_lados(
        self, harness: Harness, banco: UUID, efectivo: UUID, dolares: UUID
    ) -> None:
        """Quien mira una cuenta quiere ver tanto lo que le entró como lo que le salió."""
        await harness.unit.register_transfer.execute(DUENO, un_pedido(banco, efectivo))
        await harness.unit.register_transfer.execute(
            DUENO, un_pedido(efectivo, banco, sent=Decimal("1000.00"), received=Decimal("1000.00"))
        )

        pagina = await harness.unit.list_transfers.execute(DUENO, TransferFilters(account_id=banco))

        assert len(pagina.items) == 2

    async def test_no_devuelve_las_de_otra_persona(
        self, harness: Harness, banco: UUID, efectivo: UUID
    ) -> None:
        await harness.unit.register_transfer.execute(DUENO, un_pedido(banco, efectivo))

        pagina = await harness.unit.list_transfers.execute(OTRA_PERSONA, TransferFilters())

        assert pagina.items == []

    async def test_pagina_por_cursor(self, harness: Harness, banco: UUID, efectivo: UUID) -> None:
        for dia in (10, 11, 12):
            await harness.unit.register_transfer.execute(
                DUENO, un_pedido(banco, efectivo, occurred_on=date(2026, 9, dia))
            )

        primera = await harness.unit.list_transfers.execute(DUENO, TransferFilters(), limit=2)
        assert primera.next_cursor is not None

        segunda = await harness.unit.list_transfers.execute(
            DUENO, TransferFilters(), cursor=primera.next_cursor, limit=2
        )

        assert len(primera.items) == 2
        assert len(segunda.items) == 1
        assert segunda.next_cursor is None


def _una_categoria(harness: Harness) -> Category:
    """Una categoría de ingresos, para poder cargar un movimiento junto a la transferencia."""
    categoria = Category(
        id=uuid4(),
        owner_id=DUENO,
        name=CategoryName.parse("Sueldo"),
        kind=TransactionKind.INCOME,
        created_at=harness.clock.now(),
    )
    harness.categories.rows[categoria.id] = categoria
    return categoria


def _ingreso(account_id: UUID, category_id: UUID, amount: Decimal) -> TransactionInput:
    return TransactionInput(
        account_id=account_id,
        kind=TransactionKind.INCOME,
        amount=amount,
        category_id=category_id,
        occurred_on=a_date(),
    )
