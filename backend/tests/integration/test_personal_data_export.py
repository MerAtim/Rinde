"""Exportar los datos contra PostgreSQL real: cada fila de la persona sale (ADR-0034).

Se siembra una demo, que toca casi todas las tablas, y se le suma lo que una
demo no trae: un movimiento borrado, un lote importado con sus líneas, una regla
aprendida y una alerta. Después, tabla por tabla, la exportación tiene que traer
exactamente las filas que la base tiene de esa persona. Las tablas son las que
el candado de cobertura declara exportadas, así una tabla nueva entra sola acá.
"""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from rinde.accounts.infrastructure.tables import accounts
from rinde.alerts.domain.alert import BudgetAlert, Threshold
from rinde.alerts.infrastructure.repositories import SqlAlchemyAlertRepository
from rinde.auth.infrastructure.tables import users
from rinde.config import Settings
from rinde.imports.domain.batch import BatchLine, ImportBatch, LineStatus
from rinde.imports.domain.rules import CategoryRule
from rinde.imports.domain.statement import LineError, LineProblem
from rinde.imports.infrastructure.repositories import (
    SqlAlchemyBatchRepository,
    SqlAlchemyRuleRepository,
)
from rinde.imports.infrastructure.tables import import_batches, import_lines
from rinde.main import create_app
from rinde.rates.infrastructure.factory import SqlAlchemyRatesUnitFactory
from rinde.shared.domain.money import Currency, Money
from rinde.shared.infrastructure.clock import SystemClock
from rinde.shared.infrastructure.database import metadata
from rinde.transactions.infrastructure.tables import categories
from tests.integration.test_demo_lifecycle import _NoNetwork
from tests.unit.privacy.test_export_coverage import EXPORTED

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

CSRF = {"X-Requested-With": "rinde"}
AT = datetime(2026, 11, 10, 15, tzinfo=UTC)

# Dónde sale cada tabla exportada, para contar sus filas en el archivo.
Section = Callable[[dict[str, Any]], list[Any]]
SECTIONS: dict[str, Section] = {
    "users": lambda body: [body["profile"]],
    "accounts": lambda body: body["accounts"],
    "categories": lambda body: body["ledger"]["categories"],
    "transactions": lambda body: body["ledger"]["transactions"],
    "transfers": lambda body: body["ledger"]["transfers"],
    "installment_plans": lambda body: body["ledger"]["installment_plans"],
    "recurring_rules": lambda body: body["ledger"]["recurring_rules"],
    "transaction_audit": lambda body: body["ledger"]["transaction_history"],
    "transfer_audit": lambda body: body["ledger"]["transfer_history"],
    "budget_limits": lambda body: body["budgets"],
    "budget_alerts": lambda body: body["alerts"],
    "import_batches": lambda body: body["imports"]["batches"],
    "import_lines": lambda body: [
        line for batch in body["imports"]["batches"] for line in batch["lines"]
    ],
    "category_rules": lambda body: body["imports"]["category_rules"],
}


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


async def _rows(engine: AsyncEngine, table_name: str, user_id: UUID) -> int:
    """Las filas de la persona en una tabla: por su dueño o, en las líneas, por su lote."""
    if table_name == "import_lines":
        query = (
            select(func.count())
            .select_from(import_lines.join(import_batches))
            .where(import_batches.c.owner_id == user_id)
        )
    else:
        table = metadata.tables[table_name]
        owner = table.c.id if table_name == "users" else table.c.owner_id
        query = select(func.count()).select_from(table).where(owner == user_id)
    async with engine.connect() as connection:
        return int((await connection.execute(query)).scalar_one())


async def _add_what_a_demo_lacks(session: AsyncSession, owner_id: UUID) -> None:
    account_id = await session.scalar(
        select(accounts.c.id).where(accounts.c.owner_id == owner_id, accounts.c.currency == "ARS")
    )
    category_id = await session.scalar(
        select(categories.c.id).where(
            categories.c.owner_id == owner_id, categories.c.kind == "expense"
        )
    )
    assert account_id is not None
    assert category_id is not None
    await SqlAlchemyBatchRepository(session).add(
        ImportBatch(
            id=uuid4(),
            owner_id=owner_id,
            account_id=account_id,
            currency=Currency.ARS,
            file_name="resumen.csv",
            file_sha256="a" * 64,
            created_at=AT,
            lines=[
                BatchLine(
                    1, date(2026, 11, 2), "Farmacia", Decimal("-3200.50"), "b" * 64, LineStatus.NEW
                ),
                BatchLine(
                    2, date(2026, 11, 3), "Sueldo", Decimal("900000.00"), "c" * 64, LineStatus.NEW
                ),
            ],
            errors=[LineError(3, LineProblem.DATE_INVALID)],
        )
    )
    await SqlAlchemyRuleRepository(session).save(
        CategoryRule(
            id=uuid4(),
            owner_id=owner_id,
            pattern="farmacia",
            category_id=category_id,
            is_expense=True,
            updated_at=AT,
        )
    )
    await SqlAlchemyAlertRepository(session).add(
        BudgetAlert(
            id=uuid4(),
            owner_id=owner_id,
            category_id=category_id,
            month=date(2026, 11, 1),
            threshold=Threshold.WARNING,
            limit=Money(Decimal("100000.00"), Currency.ARS),
            spent=Money(Decimal("85000.00"), Currency.ARS),
            raised_at=AT,
        )
    )
    await session.commit()


async def _user_id(engine: AsyncEngine, username: str) -> UUID:
    async with engine.connect() as connection:
        found = await connection.execute(select(users.c.id).where(users.c.username == username))
        return UUID(str(found.scalar_one()))


async def test_the_export_has_every_row_of_the_person_and_none_of_another(
    database_url: str, engine: AsyncEngine
) -> None:
    no_network = _NoNetwork()
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app(
        Settings(environment="test", database_url=SecretStr(database_url)),
        rates_factory=SqlAlchemyRatesUnitFactory(sessions, no_network, no_network, SystemClock()),
    )
    origin = f"192.0.2.{uuid4().int % 254 + 1}"
    transport = httpx.ASGITransport(app=app, client=(origin, 50000))
    created: list[UUID] = []
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="https://testserver") as client,
    ):
        try:
            other = await client.post("/api/auth/demo", headers=CSRF)
            assert other.status_code == httpx.codes.CREATED, other.text
            other_username = other.json()["username"]
            created.append(await _user_id(engine, other_username))

            client.cookies.clear()
            seeded = await client.post("/api/auth/demo", headers=CSRF)
            assert seeded.status_code == httpx.codes.CREATED, seeded.text
            target = await _user_id(engine, seeded.json()["username"])
            created.append(target)
            async with sessions() as session:
                await _add_what_a_demo_lacks(session, target)
            first = (await client.get("/api/transactions")).json()["items"][0]["id"]
            removed = await client.delete(f"/api/transactions/{first}", headers=CSRF)
            assert removed.status_code == httpx.codes.OK, removed.text

            response = await client.get("/api/privacy/export")

            assert response.status_code == httpx.codes.OK, response.text
            body = response.json()
            counts = {name: len(SECTIONS[name](body)) for name in EXPORTED if name in SECTIONS}
            expected = {name: await _rows(engine, name, target) for name in counts}
            assert counts == expected
            # Todas las tablas declaradas tienen dónde contarse, y ninguna está vacía.
            assert set(SECTIONS) == set(EXPORTED) - {"user_preferences"}
            assert all(expected.values()), expected
            deleted = [row for row in body["ledger"]["transactions"] if row["id"] == first]
            assert deleted[0]["deleted_at"] is not None
            assert other_username not in response.text
            assert "hash" not in response.text
        finally:
            async with engine.begin() as connection:
                await connection.execute(delete(users).where(users.c.id.in_(created)))
