"""La transferencia entre cuentas propias (ADR-0014)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from rinde.shared.domain.money import Currency, Money
from rinde.transactions.domain.errors import (
    TransferAmountNotPositiveError,
    TransferCurrencyMismatchError,
    TransferDateInFutureError,
    TransferDeletedError,
    TransferSameAccountError,
)
from rinde.transactions.domain.transaction import Description, TargetAccount
from rinde.transactions.domain.transfer import (
    Transfer,
    TransferDraft,
    TransferRoute,
    register_transfer,
)

AHORA = datetime(2026, 9, 19, 15, 0, tzinfo=UTC)
HOY = AHORA.date()

BANCO = TargetAccount(id=uuid4(), currency=Currency.ARS)
EFECTIVO = TargetAccount(id=uuid4(), currency=Currency.ARS)
DOLARES = TargetAccount(id=uuid4(), currency=Currency.USD)


def pesos(monto: str) -> Money:
    return Money(Decimal(monto), Currency.ARS)


def dolares(monto: str) -> Money:
    return Money(Decimal(monto), Currency.USD)


def un_borrador(**cambios: object) -> TransferDraft:
    valores: dict[str, object] = {
        "sent": pesos("50000.00"),
        "received": pesos("50000.00"),
        "occurred_on": HOY,
        "description": None,
    }
    valores.update(cambios)
    return TransferDraft(**valores)  # type: ignore[arg-type]


def transferir(
    draft: TransferDraft | None = None,
    origen: TargetAccount = BANCO,
    destino: TargetAccount = EFECTIVO,
    owner_id: UUID | None = None,
) -> Transfer:
    return register_transfer(
        draft if draft is not None else un_borrador(),
        TransferRoute(origen, destino),
        transfer_id=uuid4(),
        owner_id=owner_id if owner_id is not None else uuid4(),
        at=AHORA,
    )


class TestRegistrar:
    def test_mueve_el_monto_de_una_cuenta_a_la_otra(self) -> None:
        transferencia = transferir()

        assert transferencia.from_account_id == BANCO.id
        assert transferencia.to_account_id == EFECTIVO.id
        assert transferencia.sent == pesos("50000.00")
        assert transferencia.received == pesos("50000.00")
        assert not transferencia.is_deleted

    def test_no_es_gasto_ni_ingreso(self) -> None:
        """Lo que le suma a cada cuenta: sale de una, entra en la otra, y el total no cambia."""
        transferencia = transferir()

        assert transferencia.effect_on(BANCO.id) == -pesos("50000.00")
        assert transferencia.effect_on(EFECTIVO.id) == pesos("50000.00")

    def test_una_cuenta_ajena_a_la_transferencia_no_se_ve_afectada(self) -> None:
        transferencia = transferir()

        assert transferencia.effect_on(DOLARES.id) is None

    def test_entre_monedas_distintas_guarda_los_dos_montos_sin_convertir(self) -> None:
        """La tasa real es la que le dieron a la persona (ADR-0014, decisión 3)."""
        draft = un_borrador(sent=pesos("100000.00"), received=dolares("80.00"))

        transferencia = transferir(draft, origen=BANCO, destino=DOLARES)

        assert transferencia.sent == pesos("100000.00")
        assert transferencia.received == dolares("80.00")
        assert transferencia.effect_on(BANCO.id) == -pesos("100000.00")
        assert transferencia.effect_on(DOLARES.id) == dolares("80.00")

    def test_admite_comision_los_dos_lados_no_tienen_por_que_coincidir(self) -> None:
        draft = un_borrador(sent=pesos("1000.00"), received=pesos("990.00"))

        transferencia = transferir(draft)

        assert transferencia.sent == pesos("1000.00")
        assert transferencia.received == pesos("990.00")

    def test_guarda_la_descripcion_normalizada(self) -> None:
        draft = un_borrador(description=Description.parse("  pase a la caja  "))

        transferencia = transferir(draft)

        assert transferencia.description == Description("pase a la caja")


class TestReglas:
    def test_no_se_puede_ni_construir_una_ruta_hacia_la_misma_cuenta(self) -> None:
        """La invariante vive en el tipo: el caso de uso no puede olvidarse de mirarla."""
        with pytest.raises(TransferSameAccountError):
            TransferRoute(BANCO, BANCO)

    @pytest.mark.parametrize("monto", ["0.00", "-1.00"])
    def test_rechaza_un_monto_que_no_sea_positivo_del_lado_que_sale(self, monto: str) -> None:
        with pytest.raises(TransferAmountNotPositiveError):
            transferir(un_borrador(sent=pesos(monto)))

    @pytest.mark.parametrize("monto", ["0.00", "-1.00"])
    def test_rechaza_un_monto_que_no_sea_positivo_del_lado_que_entra(self, monto: str) -> None:
        with pytest.raises(TransferAmountNotPositiveError):
            transferir(un_borrador(received=pesos(monto)))

    def test_rechaza_que_lo_que_sale_no_este_en_la_moneda_de_su_cuenta(self) -> None:
        with pytest.raises(TransferCurrencyMismatchError):
            transferir(un_borrador(sent=dolares("80.00")), origen=BANCO, destino=DOLARES)

    def test_rechaza_que_lo_que_entra_no_este_en_la_moneda_de_su_cuenta(self) -> None:
        with pytest.raises(TransferCurrencyMismatchError):
            transferir(un_borrador(received=dolares("80.00")), origen=BANCO, destino=EFECTIVO)

    def test_rechaza_una_fecha_futura_mas_alla_de_la_tolerancia(self) -> None:
        with pytest.raises(TransferDateInFutureError):
            transferir(un_borrador(occurred_on=date(2026, 9, 21)))

    def test_acepta_manana_por_la_diferencia_de_reloj_con_utc(self) -> None:
        """Misma tolerancia de un día que los movimientos (ADR-0011)."""
        transferencia = transferir(un_borrador(occurred_on=date(2026, 9, 20)))

        assert transferencia.occurred_on == date(2026, 9, 20)


class TestLeidaDeLaBase:
    """El repositorio construye la entidad directo: una fila corrupta no pasa."""

    def un_registro(self, **cambios: object) -> dict[str, object]:
        valores: dict[str, object] = {
            "id": uuid4(),
            "owner_id": uuid4(),
            "from_account_id": BANCO.id,
            "to_account_id": EFECTIVO.id,
            "sent": pesos("50000.00"),
            "received": pesos("50000.00"),
            "occurred_on": HOY,
            "created_at": AHORA,
            "updated_at": AHORA,
        }
        valores.update(cambios)
        return valores

    @pytest.mark.parametrize("lado", ["sent", "received"])
    def test_rechaza_un_monto_que_no_sea_positivo(self, lado: str) -> None:
        with pytest.raises(TransferAmountNotPositiveError):
            Transfer(**self.un_registro(**{lado: pesos("-1.00")}))  # type: ignore[arg-type]

    def test_rechaza_que_el_origen_y_el_destino_sean_la_misma_cuenta(self) -> None:
        with pytest.raises(TransferSameAccountError):
            Transfer(**self.un_registro(to_account_id=BANCO.id))  # type: ignore[arg-type]


class TestEditar:
    def test_edita_todo_junto_y_vuelve_a_validar(self) -> None:
        transferencia = transferir()
        despues = datetime(2026, 9, 19, 16, 0, tzinfo=UTC)

        editada = transferencia.edited(
            un_borrador(sent=pesos("60000.00"), received=pesos("60000.00")),
            TransferRoute(BANCO, EFECTIVO),
            at=despues,
        )

        assert editada.sent == pesos("60000.00")
        assert editada.updated_at == despues
        assert editada.created_at == transferencia.created_at

    def test_una_edicion_invalida_no_deja_la_transferencia_a_medias(self) -> None:
        transferencia = transferir()

        with pytest.raises(TransferAmountNotPositiveError):
            transferencia.edited(
                un_borrador(sent=pesos("0.00")), TransferRoute(BANCO, EFECTIVO), at=AHORA
            )

        assert transferencia.sent == pesos("50000.00")

    def test_no_se_edita_una_transferencia_borrada(self) -> None:
        borrada = transferir().deleted(AHORA)

        with pytest.raises(TransferDeletedError):
            borrada.edited(un_borrador(), TransferRoute(BANCO, EFECTIVO), at=AHORA)


class TestBorrar:
    def test_borrar_es_logico_y_reversible(self) -> None:
        transferencia = transferir()

        borrada = transferencia.deleted(AHORA)
        assert borrada.is_deleted

        recuperada = borrada.restored(AHORA)
        assert not recuperada.is_deleted

    def test_borrar_dos_veces_conserva_la_primera_fecha(self) -> None:
        """Idempotente, igual que los movimientos (ADR-0011, decisión 5)."""
        primera = transferir().deleted(AHORA)
        despues = datetime(2026, 9, 19, 18, 0, tzinfo=UTC)

        assert primera.deleted(despues).deleted_at == primera.deleted_at

    def test_una_transferencia_borrada_no_mueve_ningun_saldo(self) -> None:
        borrada = transferir().deleted(AHORA)

        assert borrada.effect_on(BANCO.id) is None
        assert borrada.effect_on(EFECTIVO.id) is None
