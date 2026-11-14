"""API de importación, de punta a punta con movimientos en memoria (ADR-0023)."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from rinde.config import Settings
from rinde.imports.domain.statement import MAX_BYTES
from rinde.main import create_app
from tests.fakes import (
    FakeClock,
    FakeDatabaseProbe,
    InMemoryAccountsUnitFactory,
    InMemoryAuthUnitFactory,
    InMemoryImportsUnitFactory,
    InMemoryTransactionsUnitFactory,
)
from tests.unit.imports.macro_statement import MacroStatement, to_pdf

CSRF = {"X-Requested-With": "rinde"}
PASSPHRASE = "mi gato come fideos los martes"
# Las 12 de Buenos Aires del 10 de noviembre de 2026.
NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)

LAYOUT: dict[str, Any] = {
    "delimiter": ";",
    "encoding": "windows-1252",
    "decimal_mark": "comma",
    "date_order": "dmy",
    "has_header": True,
    "date_column": 0,
    "description_column": 1,
    "amount": {"kind": "debit_credit", "debit": 2, "credit": 3},
}

# Como exporta Excel en español: punto y coma, Windows-1252 y dos columnas sin signo.
FILE = (
    "Fecha;Descripción;Débito;Crédito\n"
    "03/11/2026;PANADERÍA;1.500,00;\n"
    "05/11/2026;HABERES;;250.000,00\n"
    "07/11/2026;SIN MONTO;;\n"
).encode("cp1252")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    clock = FakeClock()
    clock.current = NOW
    accounts = InMemoryAccountsUnitFactory(clock)
    transactions = InMemoryTransactionsUnitFactory(accounts.accounts, clock)
    app = create_app(
        settings,
        database_probe=FakeDatabaseProbe(reachable=True),
        auth_factory=InMemoryAuthUnitFactory(),
        accounts_factory=accounts,
        transactions_factory=transactions,
        imports_factory=InMemoryImportsUnitFactory(transactions, clock),
    )
    with TestClient(app, base_url="https://testserver") as test_client:
        _sign_in(test_client, "mechi")
        yield test_client


def _sign_in(client: TestClient, username: str) -> None:
    client.cookies.clear()
    response = client.post(
        "/api/auth/register", json={"username": username, "password": PASSPHRASE}, headers=CSRF
    )
    assert response.status_code == status.HTTP_201_CREATED


def _account(client: TestClient, currency: str = "ARS") -> str:
    response = client.post(
        "/api/accounts",
        json={"name": f"Banco {currency}", "kind": "bank", "currency": currency},
        headers=CSRF,
    )
    identifier: str = response.json()["id"]
    return identifier


def _upload(
    client: TestClient,
    account_id: str,
    content: bytes = FILE,
    layout: dict[str, Any] | str = LAYOUT,
) -> Any:
    return client.post(
        "/api/imports",
        data={
            "account_id": account_id,
            "layout": layout if isinstance(layout, str) else json.dumps(layout),
        },
        files={"file": ("octubre.csv", content, "text/csv")},
        headers=CSRF,
    )


def _category(client: TestClient, slug: str) -> str:
    categories: list[dict[str, Any]] = client.get("/api/categories").json()
    identifier: str = next(row["id"] for row in categories if row["slug"] == slug)
    return identifier


def test_upload_shows_a_preview_with_errors_and_suggestions(client: TestClient) -> None:
    account = _account(client)

    response = _upload(client, account)

    assert response.status_code == status.HTTP_201_CREATED, response.text
    batch = response.json()
    assert batch["account_id"] == account
    assert batch["file_name"] == "octubre.csv"
    assert batch["confirmed"] is False
    assert batch["expires_at"] == "2026-11-11T15:00:00Z"
    assert batch["lines"] == [
        {
            "number": 2,
            "occurred_on": "2026-11-03",
            "description": "PANADERÍA",
            "amount": {"amount": "-1500.00", "currency": "ARS"},
            "status": "new",
            "category_id": _category(client, "otros"),
            "rule": None,
        },
        {
            "number": 3,
            "occurred_on": "2026-11-05",
            "description": "HABERES",
            "amount": {"amount": "250000.00", "currency": "ARS"},
            "status": "new",
            "category_id": _category(client, "otros-ingresos"),
            "rule": None,
        },
    ]
    assert batch["errors"] == [{"line": 4, "problem": "LINE_AMOUNT_ZERO"}]
    assert client.get(f"/api/imports/{batch['id']}").json() == batch


def test_confirming_registers_the_movements_once(client: TestClient) -> None:
    account = _account(client)
    batch = _upload(client, account).json()
    choices = {"lines": [{"number": 2, "category_id": _category(client, "supermercado")}]}

    first = client.post(f"/api/imports/{batch['id']}/confirm", json=choices, headers=CSRF)
    again = client.post(f"/api/imports/{batch['id']}/confirm", json=choices, headers=CSRF)

    assert first.status_code == status.HTTP_200_OK, first.text
    assert first.json() == {"imported": 1, "skipped": 0}
    assert again.json() == {"imported": 1, "skipped": 0}
    [movement] = client.get("/api/transactions").json()["items"]
    assert movement["kind"] == "expense"
    assert movement["amount"] == "1500.00"
    assert movement["description"] == "PANADERÍA"
    assert movement["category_id"] == _category(client, "supermercado")
    assert client.get(f"/api/imports/{batch['id']}").json()["confirmed"] is True


def test_the_same_file_again_is_marked_as_duplicate(client: TestClient) -> None:
    account = _account(client)
    batch = _upload(client, account).json()
    client.post(
        f"/api/imports/{batch['id']}/confirm",
        json={"lines": [{"number": 2, "category_id": _category(client, "otros")}]},
        headers=CSRF,
    )

    second = _upload(client, account).json()

    assert [line["status"] for line in second["lines"]] == ["duplicate", "new"]


def test_a_category_of_the_wrong_kind_rejects_the_whole_batch(client: TestClient) -> None:
    account = _account(client)
    batch = _upload(client, account).json()

    response = client.post(
        f"/api/imports/{batch['id']}/confirm",
        json={
            "lines": [
                {"number": 2, "category_id": _category(client, "otros")},
                {"number": 3, "category_id": _category(client, "otros")},
            ]
        },
        headers=CSRF,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {"code": "CATEGORY_KIND_MISMATCH"}
    # Que no quede ninguno a medias lo prueba el caso de uso: no confirma la
    # transacción. La memoria de este test no deshace como una base.
    assert client.get(f"/api/imports/{batch['id']}").json()["confirmed"] is False


@pytest.mark.parametrize(
    ("content", "layout", "code"),
    [
        (FILE, "{no es json", "IMPORT_LAYOUT_INVALID"),
        (FILE, {**LAYOUT, "description_column": 0}, "IMPORT_LAYOUT_INVALID"),
        (FILE, {**LAYOUT, "extra": True}, "IMPORT_LAYOUT_INVALID"),
        (FILE, {**LAYOUT, "encoding": "utf-8"}, "IMPORT_ENCODING_INVALID"),
        (b"Fecha;Desc;Deb;Cred\n", LAYOUT, "IMPORT_FILE_EMPTY"),
        (FILE, {**LAYOUT, "delimiter": ","}, "IMPORT_NOTHING_READABLE"),
    ],
)
def test_a_file_that_cannot_be_read_says_why(
    client: TestClient, content: bytes, layout: dict[str, Any] | str, code: str
) -> None:
    response = _upload(client, _account(client), content, layout)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {"code": code}


def test_a_file_over_the_limit(client: TestClient) -> None:
    response = _upload(client, _account(client), b"x" * (MAX_BYTES + 1))

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert response.json() == {"code": "IMPORT_FILE_TOO_LARGE"}


def test_a_body_far_over_the_limit_is_cut_before_reading(client: TestClient) -> None:
    response = _upload(client, _account(client), b"x" * (MAX_BYTES * 2))

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert response.json() == {"code": "REQUEST_TOO_LARGE"}


def test_importing_into_an_account_of_another_person(client: TestClient) -> None:
    theirs = _account(client)
    _sign_in(client, "otra")

    response = _upload(client, theirs)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"code": "ACCOUNT_NOT_FOUND"}


def test_a_pending_batch_can_be_discarded(client: TestClient) -> None:
    batch = _upload(client, _account(client)).json()

    discarded = client.delete(f"/api/imports/{batch['id']}", headers=CSRF)
    again = client.delete(f"/api/imports/{batch['id']}", headers=CSRF)

    assert discarded.status_code == status.HTTP_204_NO_CONTENT
    assert again.status_code == status.HTTP_404_NOT_FOUND
    assert again.json() == {"code": "IMPORT_BATCH_NOT_FOUND"}


def test_confirming_a_line_that_is_not_in_the_batch(client: TestClient) -> None:
    batch = _upload(client, _account(client)).json()

    response = client.post(
        f"/api/imports/{batch['id']}/confirm",
        json={"lines": [{"number": 4, "category_id": _category(client, "otros")}]},
        headers=CSRF,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {"code": "IMPORT_LINE_NOT_FOUND"}


def test_uploading_needs_the_csrf_header(client: TestClient) -> None:
    response = client.post(
        "/api/imports",
        data={"account_id": _account(client), "layout": json.dumps(LAYOUT)},
        files={"file": ("octubre.csv", FILE, "text/csv")},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_a_remembered_rule_categorizes_the_next_import(client: TestClient) -> None:
    account = _account(client)
    food = _category(client, "supermercado")
    batch = _upload(client, account).json()
    client.post(
        f"/api/imports/{batch['id']}/confirm",
        json={"lines": [{"number": 2, "category_id": food, "remember": "Panadería"}]},
        headers=CSRF,
    )

    other_account = _account(client, "USD")
    usd = ("Fecha;Descripción;Débito;Crédito\n03/11/2026;PANADERÍA CENTRO;15,00;\n").encode(
        "cp1252"
    )
    second = _upload(client, other_account, usd).json()

    [line] = second["lines"]
    assert line["category_id"] == food
    assert line["rule"] == "panaderia"


def test_a_text_too_short_to_remember(client: TestClient) -> None:
    batch = _upload(client, _account(client)).json()

    response = client.post(
        f"/api/imports/{batch['id']}/confirm",
        json={
            "lines": [{"number": 2, "category_id": _category(client, "otros"), "remember": "ab"}]
        },
        headers=CSRF,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {"code": "IMPORT_RULE_PATTERN_INVALID"}


def _upload_pdf(client: TestClient, account_id: str, content: bytes, **fields: str) -> Any:
    return client.post(
        "/api/imports",
        data={"account_id": account_id, "format": "macro_pdf", **fields},
        files={"file": ("resumen.pdf", content, "application/pdf")},
        headers=CSRF,
    )


class TestResumenPdf:
    def test_the_macro_statement_shows_a_preview(self, client: TestClient) -> None:
        source = MacroStatement()

        response = _upload_pdf(client, _account(client), to_pdf(source.pages()))

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["file_name"] == "resumen.pdf"
        assert [line["amount"]["amount"] for line in body["lines"]] == [
            "-1500.00",
            "250000.00",
            "-12345.67",
        ]
        assert body["errors"] == []

    @pytest.mark.parametrize(
        ("content", "code"),
        [
            (FILE, "IMPORT_PDF_INVALID"),
            (to_pdf([[]]), "IMPORT_STATEMENT_UNKNOWN"),
            (
                to_pdf(
                    MacroStatement(
                        totals=(Decimal("2500.00"), Decimal(1), Decimal(1), Decimal("2500.00"))
                    ).pages()
                ),
                "IMPORT_STATEMENT_UNBALANCED",
            ),
            (
                to_pdf([*MacroStatement().pages(), *MacroStatement(currency="DOLARES").pages()]),
                "IMPORT_STATEMENT_MULTIPLE_ACCOUNTS",
            ),
        ],
        ids=["no es PDF", "sin texto", "no cierra", "dos cuentas"],
    )
    def test_a_statement_that_cannot_be_trusted_says_why(
        self, client: TestClient, content: bytes, code: str
    ) -> None:
        response = _upload_pdf(client, _account(client), content)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {"code": code}

    def test_a_statement_in_pesos_into_an_account_in_dollars(self, client: TestClient) -> None:
        response = _upload_pdf(client, _account(client, "USD"), to_pdf(MacroStatement().pages()))

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {"code": "IMPORT_CURRENCY_MISMATCH"}

    def test_a_layout_with_a_pdf_is_a_confused_request(self, client: TestClient) -> None:
        response = _upload_pdf(
            client, _account(client), to_pdf(MacroStatement().pages()), layout=json.dumps(LAYOUT)
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {"code": "IMPORT_LAYOUT_INVALID"}

    def test_a_csv_needs_its_layout(self, client: TestClient) -> None:
        response = client.post(
            "/api/imports",
            data={"account_id": _account(client), "format": "csv"},
            files={"file": ("octubre.csv", FILE, "text/csv")},
            headers=CSRF,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {"code": "IMPORT_LAYOUT_INVALID"}

    def test_a_statement_of_another_person_account(self, client: TestClient) -> None:
        theirs = _account(client)
        _sign_in(client, "otra")

        response = _upload_pdf(client, theirs, to_pdf(MacroStatement().pages()))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"code": "ACCOUNT_NOT_FOUND"}
