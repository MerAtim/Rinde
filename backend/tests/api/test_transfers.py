"""API de transferencias (ADR-0014)."""

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from rinde.config import Settings
from rinde.main import create_app
from tests.fakes import (
    FakeDatabaseProbe,
    InMemoryAccountsUnitFactory,
    InMemoryAuthUnitFactory,
    InMemoryTransactionsUnitFactory,
)

CSRF = {"X-Requested-With": "rinde"}
PASSPHRASE = "mi gato come fideos los martes"


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    accounts_factory = InMemoryAccountsUnitFactory()
    return create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=InMemoryAuthUnitFactory(),
        accounts_factory=accounts_factory,
        transactions_factory=InMemoryTransactionsUnitFactory(accounts_factory.accounts),
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def signed_in(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/register", json={"username": "mechi", "password": PASSPHRASE}, headers=CSRF
    )
    assert response.status_code == status.HTTP_201_CREATED
    return client


def _account(client: TestClient, currency: str = "ARS") -> str:
    response = client.post(
        "/api/accounts",
        json={"name": f"Cuenta {uuid4().hex[:6]}", "kind": "bank", "currency": currency},
        headers=CSRF,
    )
    assert response.status_code == status.HTTP_201_CREATED
    identifier: str = response.json()["id"]
    return identifier


def _body(origen: str, destino: str, **cambios: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "from_account_id": origen,
        "to_account_id": destino,
        "sent": "50000.00",
        "received": "50000.00",
        "occurred_on": "2026-09-11",
    }
    payload.update(cambios)
    return payload


class TestRegistrar:
    def test_devuelve_los_dos_lados_como_string_decimal(self, signed_in: TestClient) -> None:
        banco, dolares = _account(signed_in), _account(signed_in, "USD")

        response = signed_in.post(
            "/api/transfers",
            json=_body(banco, dolares, sent="100000.00", received="80.00"),
            headers=CSRF,
        )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["sent"] == "100000.00"
        assert body["currency_out"] == "ARS"
        assert body["received"] == "80.00"
        assert body["currency_in"] == "USD"

    def test_mueve_el_saldo_de_las_dos_cuentas(self, signed_in: TestClient) -> None:
        banco, efectivo = _account(signed_in), _account(signed_in)
        signed_in.post("/api/transfers", json=_body(banco, efectivo), headers=CSRF)

        saldos = {
            row["account_id"]: row["amount"]
            for row in signed_in.get("/api/transactions/balances").json()
        }

        assert saldos[banco] == "-50000.00"
        assert saldos[efectivo] == "50000.00"

    def test_no_aparece_entre_los_movimientos(self, signed_in: TestClient) -> None:
        """Una transferencia no es gasto ni ingreso: ningún reporte la puede ver."""
        banco, efectivo = _account(signed_in), _account(signed_in)
        signed_in.post("/api/transfers", json=_body(banco, efectivo), headers=CSRF)

        assert signed_in.get("/api/transactions").json()["items"] == []

    def test_un_reintento_con_la_misma_clave_no_duplica(self, signed_in: TestClient) -> None:
        banco, efectivo = _account(signed_in), _account(signed_in)
        headers = CSRF | {"Idempotency-Key": "clave-1"}
        payload = _body(banco, efectivo)

        primera = signed_in.post("/api/transfers", json=payload, headers=headers)
        segunda = signed_in.post("/api/transfers", json=payload, headers=headers)

        assert primera.json()["id"] == segunda.json()["id"]
        assert len(signed_in.get("/api/transfers").json()["items"]) == 1

    def test_la_misma_clave_con_otro_cuerpo_es_un_conflicto(self, signed_in: TestClient) -> None:
        banco, efectivo = _account(signed_in), _account(signed_in)
        headers = CSRF | {"Idempotency-Key": "clave-1"}
        signed_in.post("/api/transfers", json=_body(banco, efectivo), headers=headers)

        response = signed_in.post(
            "/api/transfers", json=_body(banco, efectivo, sent="999.00"), headers=headers
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


class TestValidacion:
    def test_un_monto_numerico_se_rechaza_en_el_borde(self, signed_in: TestClient) -> None:
        """Un número en JSON pasa por el double de JavaScript y pierde centavos."""
        banco, efectivo = _account(signed_in), _account(signed_in)

        response = signed_in.post(
            "/api/transfers", json=_body(banco, efectivo, sent=50000.0), headers=CSRF
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_la_misma_cuenta_de_los_dos_lados_se_rechaza(self, signed_in: TestClient) -> None:
        banco = _account(signed_in)

        response = signed_in.post("/api/transfers", json=_body(banco, banco), headers=CSRF)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["code"] == "TRANSFER_SAME_ACCOUNT"

    def test_un_monto_cero_se_rechaza(self, signed_in: TestClient) -> None:
        banco, efectivo = _account(signed_in), _account(signed_in)

        response = signed_in.post(
            "/api/transfers", json=_body(banco, efectivo, received="0.00"), headers=CSRF
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["code"] == "TRANSFER_AMOUNT_NOT_POSITIVE"

    def test_una_cuenta_inexistente_se_informa_como_no_encontrada(
        self, signed_in: TestClient
    ) -> None:
        banco = _account(signed_in)

        response = signed_in.post("/api/transfers", json=_body(banco, str(uuid4())), headers=CSRF)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["code"] == "ACCOUNT_NOT_FOUND"

    def test_una_cuenta_archivada_no_recibe(self, signed_in: TestClient) -> None:
        banco, archivada = _account(signed_in), _account(signed_in)
        signed_in.post(f"/api/accounts/{archivada}/archive", headers=CSRF)

        response = signed_in.post("/api/transfers", json=_body(banco, archivada), headers=CSRF)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["code"] == "ACCOUNT_ARCHIVED"

    def test_una_fecha_futura_se_rechaza(self, signed_in: TestClient) -> None:
        banco, efectivo = _account(signed_in), _account(signed_in)

        response = signed_in.post(
            "/api/transfers",
            json=_body(banco, efectivo, occurred_on="2030-01-01"),
            headers=CSRF,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json()["code"] == "TRANSFER_DATE_IN_FUTURE"


class TestEditarYBorrar:
    def test_corrige_las_cuentas_elegidas(self, signed_in: TestClient) -> None:
        banco, efectivo, dolares = (
            _account(signed_in),
            _account(signed_in),
            _account(signed_in, "USD"),
        )
        creada = signed_in.post("/api/transfers", json=_body(banco, efectivo), headers=CSRF).json()

        response = signed_in.patch(
            f"/api/transfers/{creada['id']}",
            json=_body(banco, dolares, sent="50000.00", received="40.00"),
            headers=CSRF,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["to_account_id"] == dolares
        assert response.json()["currency_in"] == "USD"

    def test_borrar_y_deshacer_devuelve_el_saldo(self, signed_in: TestClient) -> None:
        banco, efectivo = _account(signed_in), _account(signed_in)
        creada = signed_in.post("/api/transfers", json=_body(banco, efectivo), headers=CSRF).json()

        signed_in.delete(f"/api/transfers/{creada['id']}", headers=CSRF)
        assert signed_in.get("/api/transactions/balances").json() == []

        signed_in.post(f"/api/transfers/{creada['id']}/restore", headers=CSRF)
        saldos = {
            row["account_id"]: row["amount"]
            for row in signed_in.get("/api/transactions/balances").json()
        }
        assert saldos[efectivo] == "50000.00"

    def test_una_transferencia_borrada_ya_no_se_consulta(self, signed_in: TestClient) -> None:
        banco, efectivo = _account(signed_in), _account(signed_in)
        creada = signed_in.post("/api/transfers", json=_body(banco, efectivo), headers=CSRF).json()
        signed_in.delete(f"/api/transfers/{creada['id']}", headers=CSRF)

        response = signed_in.get(f"/api/transfers/{creada['id']}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["code"] == "TRANSFER_NOT_FOUND"


class TestHistorial:
    """`/api/history` mezcla las dos cosas; `/api/transactions` sigue sin verlas."""

    def _un_gasto(self, client: TestClient, cuenta: str) -> None:
        categoria: str = client.post(
            "/api/categories",
            json={"name": f"Categoría {uuid4().hex[:8]}", "kind": "expense"},
            headers=CSRF,
        ).json()["id"]
        client.post(
            "/api/transactions",
            json={
                "account_id": cuenta,
                "kind": "expense",
                "amount": "1500.00",
                "category_id": categoria,
                "occurred_on": "2026-09-10",
            },
            headers=CSRF,
        )

    def test_devuelve_las_dos_cosas_con_su_tipo(self, signed_in: TestClient) -> None:
        banco, efectivo = _account(signed_in), _account(signed_in)
        self._un_gasto(signed_in, banco)
        signed_in.post("/api/transfers", json=_body(banco, efectivo), headers=CSRF)

        items = signed_in.get("/api/history").json()["items"]

        # La transferencia es del 11 y el gasto del 10: primero la más nueva.
        assert [item["type"] for item in items] == ["transfer", "transaction"]
        assert items[0]["transfer"]["sent"] == "50000.00"
        assert items[1]["transaction"]["amount"] == "1500.00"

    def test_la_lista_de_movimientos_sigue_sin_transferencias(self, signed_in: TestClient) -> None:
        """Es la razón de ser del modelo: un reporte de gastos no las puede ver."""
        banco, efectivo = _account(signed_in), _account(signed_in)
        self._un_gasto(signed_in, banco)
        signed_in.post("/api/transfers", json=_body(banco, efectivo), headers=CSRF)

        movimientos = signed_in.get("/api/transactions").json()["items"]

        assert len(movimientos) == 1
        assert movimientos[0]["amount"] == "1500.00"

    def test_la_cuenta_filtra_las_dos_fuentes(self, signed_in: TestClient) -> None:
        banco, efectivo, otra = _account(signed_in), _account(signed_in), _account(signed_in)
        self._un_gasto(signed_in, banco)
        signed_in.post("/api/transfers", json=_body(efectivo, otra), headers=CSRF)

        items = signed_in.get(f"/api/history?account_id={banco}").json()["items"]

        assert [item["type"] for item in items] == ["transaction"]

    def test_sin_sesion_responde_401(self, client: TestClient) -> None:
        assert client.get("/api/history").status_code == status.HTTP_401_UNAUTHORIZED


class TestFiltros:
    def _un_gasto(self, client: TestClient, cuenta: str, descripcion: str) -> str:
        categoria: str = client.post(
            "/api/categories",
            json={"name": f"Categoría {uuid4().hex[:8]}", "kind": "expense"},
            headers=CSRF,
        ).json()["id"]
        client.post(
            "/api/transactions",
            json={
                "account_id": cuenta,
                "kind": "expense",
                "amount": "1500.00",
                "category_id": categoria,
                "occurred_on": "2026-09-10",
                "description": descripcion,
            },
            headers=CSRF,
        )
        return categoria

    def test_busca_sin_distinguir_tildes(self, signed_in: TestClient) -> None:
        banco = _account(signed_in)
        self._un_gasto(signed_in, banco, "Panadería del barrio")
        self._un_gasto(signed_in, banco, "Verdulería")

        items = signed_in.get("/api/history?q=panaderia").json()["items"]

        assert [item["transaction"]["description"] for item in items] == ["Panadería del barrio"]

    def test_busca_tambien_en_las_transferencias(self, signed_in: TestClient) -> None:
        banco, efectivo = _account(signed_in), _account(signed_in)
        self._un_gasto(signed_in, banco, "Pago de la panadería")
        signed_in.post(
            "/api/transfers",
            json=_body(banco, efectivo, description="Plata para la panadería"),
            headers=CSRF,
        )

        items = signed_in.get("/api/history?q=panaderia").json()["items"]

        assert sorted(item["type"] for item in items) == ["transaction", "transfer"]

    def test_filtrar_por_categoria_deja_afuera_las_transferencias(
        self, signed_in: TestClient
    ) -> None:
        banco, efectivo = _account(signed_in), _account(signed_in)
        categoria = self._un_gasto(signed_in, banco, "Coto")
        signed_in.post("/api/transfers", json=_body(banco, efectivo), headers=CSRF)

        items = signed_in.get(f"/api/history?category_id={categoria}").json()["items"]

        assert [item["type"] for item in items] == ["transaction"]

    def test_un_parametro_desconocido_se_rechaza(self, signed_in: TestClient) -> None:
        """La consulta prohíbe lo que no conoce: un filtro mal escrito se nota."""
        response = signed_in.get("/api/history?categoria=lo-que-sea")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestListar:
    def test_la_cuenta_filtra_de_los_dos_lados(self, signed_in: TestClient) -> None:
        banco, efectivo, otra = _account(signed_in), _account(signed_in), _account(signed_in)
        signed_in.post("/api/transfers", json=_body(banco, efectivo), headers=CSRF)
        signed_in.post("/api/transfers", json=_body(efectivo, banco), headers=CSRF)
        signed_in.post("/api/transfers", json=_body(efectivo, otra), headers=CSRF)

        response = signed_in.get(f"/api/transfers?account_id={banco}")

        assert len(response.json()["items"]) == 2

    def test_sin_sesion_responde_401(self, client: TestClient) -> None:
        assert client.get("/api/transfers").status_code == status.HTTP_401_UNAUTHORIZED

    def test_sin_el_encabezado_csrf_no_se_registra(self, signed_in: TestClient) -> None:
        banco, efectivo = _account(signed_in), _account(signed_in)

        response = signed_in.post("/api/transfers", json=_body(banco, efectivo))

        assert response.status_code == status.HTTP_403_FORBIDDEN
