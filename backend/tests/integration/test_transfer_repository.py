"""Repositorio de transferencias contra PostgreSQL real (ADR-0014).

Acá se prueba lo que un doble en memoria no puede probar: que las restricciones
de la base sostengan las reglas aunque alguien escriba sin pasar por el dominio,
y que el saldo, que suma dos mitades, cierre exacto.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from rinde.accounts.infrastructure.tables import accounts
from rinde.auth.infrastructure.tables import users
from rinde.shared.domain.money import Currency, Money
from rinde.transactions.application.ports import TransferFilters
from rinde.transactions.domain.transaction import AuditAction, Description, TargetAccount
from rinde.transactions.domain.transfer import (
    Transfer,
    TransferDraft,
    TransferRoute,
    register_transfer,
)
from rinde.transactions.infrastructure.repositories import (
    SqlAlchemyTransferAuditLog,
    SqlAlchemyTransferRepository,
)
from rinde.transactions.infrastructure.tables import transfer_audit, transfers

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

NOW = datetime(2026, 9, 19, 12, tzinfo=UTC)


@pytest.fixture
async def session(database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        db_session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield db_session
        finally:
            await db_session.close()
            await transaction.rollback()
    await engine.dispose()


async def _user(session: AsyncSession, name: str) -> UUID:
    user_id = uuid4()
    await session.execute(
        insert(users).values(
            id=user_id,
            username=name,
            password_hash="x",
            recovery_code_hash="x",
            created_at=NOW,
        )
    )
    return user_id


async def _account(
    session: AsyncSession, owner_id: UUID, currency: Currency = Currency.ARS
) -> TargetAccount:
    account_id = uuid4()
    await session.execute(
        insert(accounts).values(
            id=account_id,
            owner_id=owner_id,
            name="Cuenta",
            kind="bank" if currency is not Currency.BTC else "crypto_wallet",
            currency=currency.value,
            created_at=NOW,
        )
    )
    return TargetAccount(id=account_id, currency=currency)


def _a_transfer(
    owner_id: UUID,
    route: TransferRoute,
    sent: str = "50000.00",
    received: str | None = None,
    day: int = 19,
) -> Transfer:
    draft = TransferDraft(
        sent=Money(Decimal(sent), route.origin.currency),
        received=Money(
            Decimal(received if received is not None else sent), route.destination.currency
        ),
        occurred_on=date(2026, 9, day),
        description=Description.parse("pase a la caja"),
    )
    return register_transfer(draft, route, transfer_id=uuid4(), owner_id=owner_id, at=NOW)


class TestGuardarYLeer:
    async def test_guarda_y_devuelve_los_dos_lados_exactos(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        banco = await _account(session, owner_id)
        dolares = await _account(session, owner_id, Currency.USD)
        repository = SqlAlchemyTransferRepository(session)
        transferencia = _a_transfer(owner_id, TransferRoute(banco, dolares), "100000.00", "80.00")

        await repository.add(transferencia)

        leida = await repository.get(transferencia.id, owner_id)
        assert leida is not None
        assert leida.sent == Money(Decimal("100000.00"), Currency.ARS)
        assert leida.received == Money(Decimal("80.00"), Currency.USD)
        assert leida.description == Description("pase a la caja")

    async def test_una_transferencia_ajena_no_se_lee(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        otra = await _user(session, "leonel")
        banco = await _account(session, owner_id)
        efectivo = await _account(session, owner_id)
        repository = SqlAlchemyTransferRepository(session)
        transferencia = _a_transfer(owner_id, TransferRoute(banco, efectivo))
        await repository.add(transferencia)

        assert await repository.get(transferencia.id, otra) is None

    async def test_el_monto_de_bitcoin_conserva_sus_ocho_decimales(
        self, session: AsyncSession
    ) -> None:
        owner_id = await _user(session, "mechi")
        lemon = await _account(session, owner_id, Currency.BTC)
        otra_cripto = await _account(session, owner_id, Currency.BTC)
        repository = SqlAlchemyTransferRepository(session)
        transferencia = _a_transfer(owner_id, TransferRoute(lemon, otra_cripto), "0.00123456")

        await repository.add(transferencia)

        leida = await repository.get(transferencia.id, owner_id)
        assert leida is not None
        assert leida.sent == Money(Decimal("0.00123456"), Currency.BTC)


class TestElBorradoLogicoSeFiltra:
    """Por cada lectura, una transferencia borrada que no tiene que aparecer."""

    async def test_no_aparece_en_la_lista(self, session: AsyncSession) -> None:
        caso = await _una_viva_y_una_borrada(session)

        pagina = await caso.repository.page_for_owner(
            caso.owner_id, TransferFilters(), cursor=None, limit=50
        )

        assert [row.id for row in pagina.items] == [caso.viva.id]

    async def test_no_cuenta_en_el_saldo(self, session: AsyncSession) -> None:
        caso = await _una_viva_y_una_borrada(session)

        saldos = {
            b.account_id: b.balance for b in await caso.repository.balances_for_owner(caso.owner_id)
        }

        # Solo la viva. Si la borrada contara, serian -50777 y 50777.
        assert saldos[caso.origen.id] == Money(Decimal("-50000.00"), Currency.ARS)
        assert saldos[caso.destino.id] == Money(Decimal("50000.00"), Currency.ARS)

    async def test_se_sigue_pudiendo_leer_por_id_para_deshacer(self, session: AsyncSession) -> None:
        caso = await _una_viva_y_una_borrada(session)

        leida = await caso.repository.get(caso.borrada.id, caso.owner_id)

        assert leida is not None
        assert leida.is_deleted


class TestSaldo:
    async def test_suma_lo_que_entro_y_resta_lo_que_salio(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        banco = await _account(session, owner_id)
        efectivo = await _account(session, owner_id)
        repository = SqlAlchemyTransferRepository(session)
        await repository.add(_a_transfer(owner_id, TransferRoute(banco, efectivo), "50000.00"))
        await repository.add(_a_transfer(owner_id, TransferRoute(efectivo, banco), "20000.00"))

        saldos = {b.account_id: b.balance for b in await repository.balances_for_owner(owner_id)}

        assert saldos[banco.id] == Money(Decimal("-30000.00"), Currency.ARS)
        assert saldos[efectivo.id] == Money(Decimal("30000.00"), Currency.ARS)

    async def test_entre_monedas_cada_lado_queda_en_la_suya(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        banco = await _account(session, owner_id)
        dolares = await _account(session, owner_id, Currency.USD)
        repository = SqlAlchemyTransferRepository(session)
        await repository.add(
            _a_transfer(owner_id, TransferRoute(banco, dolares), "100000.00", "80.00")
        )

        saldos = {b.account_id: b.balance for b in await repository.balances_for_owner(owner_id)}

        assert saldos[banco.id] == Money(Decimal("-100000.00"), Currency.ARS)
        assert saldos[dolares.id] == Money(Decimal("80.00"), Currency.USD)


class TestListado:
    async def test_la_cuenta_filtra_de_los_dos_lados(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        banco = await _account(session, owner_id)
        efectivo = await _account(session, owner_id)
        ajena = await _account(session, owner_id)
        repository = SqlAlchemyTransferRepository(session)
        await repository.add(_a_transfer(owner_id, TransferRoute(banco, efectivo), day=18))
        await repository.add(_a_transfer(owner_id, TransferRoute(efectivo, banco), day=17))
        await repository.add(_a_transfer(owner_id, TransferRoute(efectivo, ajena), day=16))

        pagina = await repository.page_for_owner(
            owner_id, TransferFilters(account_id=banco.id), cursor=None, limit=50
        )

        assert len(pagina.items) == 2

    async def test_pagina_por_cursor_sin_repetir_ni_saltear(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        banco = await _account(session, owner_id)
        efectivo = await _account(session, owner_id)
        repository = SqlAlchemyTransferRepository(session)
        for dia in (15, 16, 17):
            await repository.add(_a_transfer(owner_id, TransferRoute(banco, efectivo), day=dia))

        primera = await repository.page_for_owner(owner_id, TransferFilters(), cursor=None, limit=2)
        assert primera.next_cursor is not None
        segunda = await repository.page_for_owner(
            owner_id, TransferFilters(), cursor=primera.next_cursor, limit=2
        )

        vistas = [row.id for row in primera.items] + [row.id for row in segunda.items]
        assert len(vistas) == len(set(vistas)) == 3
        assert segunda.next_cursor is None


class TestLaBaseSostieneLasReglas:
    """Escrituras que no pasan por el dominio: la base las tiene que rechazar igual."""

    async def test_rechaza_la_misma_cuenta_de_origen_y_destino(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        banco = await _account(session, owner_id)

        with pytest.raises(IntegrityError):
            await session.execute(insert(transfers).values(**_crudo(owner_id, banco, banco)))

    async def test_rechaza_un_monto_que_no_sea_positivo(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        banco = await _account(session, owner_id)
        efectivo = await _account(session, owner_id)
        valores = _crudo(owner_id, banco, efectivo) | {"amount_out": Decimal("0")}

        with pytest.raises(IntegrityError):
            await session.execute(insert(transfers).values(**valores))

    async def test_rechaza_una_moneda_que_no_es_la_de_su_cuenta(
        self, session: AsyncSession
    ) -> None:
        """La clave foránea compuesta ata cada lado a la moneda de su cuenta."""
        owner_id = await _user(session, "mechi")
        banco = await _account(session, owner_id)
        efectivo = await _account(session, owner_id)
        valores = _crudo(owner_id, banco, efectivo) | {"currency_out": "USD"}

        with pytest.raises(IntegrityError):
            await session.execute(insert(transfers).values(**valores))

    async def test_rechaza_una_cuenta_de_otra_persona(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        otra = await _user(session, "leonel")
        banco = await _account(session, owner_id)
        ajena = await _account(session, otra)

        with pytest.raises(IntegrityError):
            await session.execute(insert(transfers).values(**_crudo(owner_id, banco, ajena)))


class TestAuditoria:
    async def test_registra_la_accion_con_su_foto(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        banco = await _account(session, owner_id)
        efectivo = await _account(session, owner_id)
        transferencia = _a_transfer(owner_id, TransferRoute(banco, efectivo))
        await SqlAlchemyTransferRepository(session).add(transferencia)

        await SqlAlchemyTransferAuditLog(session).record(AuditAction.REGISTERED, transferencia, NOW)

        result = await session.execute(
            select(transfer_audit.c.action, transfer_audit.c.snapshot).where(
                transfer_audit.c.transfer_id == transferencia.id
            )
        )
        action, snapshot = result.one()
        assert action == "registered"
        assert snapshot["amount_out"] == "50000.00"
        assert snapshot["currency_in"] == "ARS"

    async def test_el_log_no_se_puede_modificar_ni_borrar(self, session: AsyncSession) -> None:
        """La regla vale también desde psql: la sostiene un disparador."""
        owner_id = await _user(session, "mechi")
        banco = await _account(session, owner_id)
        efectivo = await _account(session, owner_id)
        transferencia = _a_transfer(owner_id, TransferRoute(banco, efectivo))
        await SqlAlchemyTransferRepository(session).add(transferencia)
        await SqlAlchemyTransferAuditLog(session).record(AuditAction.REGISTERED, transferencia, NOW)

        with pytest.raises(DBAPIError):
            await session.execute(
                update(transfer_audit)
                .where(transfer_audit.c.transfer_id == transferencia.id)
                .values(action="edited")
            )


def _crudo(owner_id: UUID, origin: TargetAccount, destination: TargetAccount) -> dict[str, object]:
    """Los valores de una fila, para escribir sin pasar por el dominio."""
    return {
        "id": uuid4(),
        "owner_id": owner_id,
        "from_account_id": origin.id,
        "currency_out": origin.currency.value,
        "amount_out": Decimal("1000.00"),
        "to_account_id": destination.id,
        "currency_in": destination.currency.value,
        "amount_in": Decimal("1000.00"),
        "occurred_on": date(2026, 9, 19),
        "description": None,
        "created_at": NOW,
        "updated_at": NOW,
        "deleted_at": None,
    }


@dataclass(frozen=True, slots=True)
class Escenario:
    """Una transferencia viva de 50000 y otra borrada de 777, entre las mismas cuentas."""

    owner_id: UUID
    repository: SqlAlchemyTransferRepository
    origen: TargetAccount
    destino: TargetAccount
    viva: Transfer
    borrada: Transfer


async def _una_viva_y_una_borrada(session: AsyncSession) -> Escenario:
    owner_id = await _user(session, "mechi")
    banco = await _account(session, owner_id)
    efectivo = await _account(session, owner_id)
    repository = SqlAlchemyTransferRepository(session)
    viva = _a_transfer(owner_id, TransferRoute(banco, efectivo), day=19)
    borrada = _a_transfer(owner_id, TransferRoute(banco, efectivo), "777.00", day=18).deleted(NOW)
    await repository.add(viva)
    await repository.add(borrada)
    return Escenario(owner_id, repository, banco, efectivo, viva, borrada)
