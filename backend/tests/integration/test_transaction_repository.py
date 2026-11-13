"""Repositorios de movimientos contra PostgreSQL real. Cada test se deshace al terminar."""

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from rinde.accounts.infrastructure.tables import accounts
from rinde.auth.infrastructure.tables import users
from rinde.shared.domain.money import Currency, Money
from rinde.transactions.application.ports import (
    BalanceChange,
    IdempotentResource,
    LedgerScope,
    RememberedKey,
    TransactionFilters,
)
from rinde.transactions.domain.category import Category, CategoryName, TransactionKind
from rinde.transactions.domain.errors import TransactionAlreadyImportedError
from rinde.transactions.domain.transaction import (
    AuditAction,
    Description,
    Draft,
    TargetAccount,
    Transaction,
    register,
)
from rinde.transactions.infrastructure.repositories import (
    SqlAlchemyAuditLog,
    SqlAlchemyCategoryRepository,
    SqlAlchemyIdempotencyStore,
    SqlAlchemyTransactionRepository,
)
from rinde.transactions.infrastructure.tables import transaction_audit, transactions

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)


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
            name="Galicia sueldo",
            kind="bank",
            currency=currency.value,
            created_at=NOW,
        )
    )
    return TargetAccount(id=account_id, currency=currency)


async def _category(
    session: AsyncSession,
    owner_id: UUID,
    kind: TransactionKind = TransactionKind.EXPENSE,
    name: str = "Supermercado",
) -> Category:
    category = Category(
        id=uuid4(),
        owner_id=owner_id,
        name=CategoryName.parse(name),
        kind=kind,
        created_at=NOW,
    )
    await SqlAlchemyCategoryRepository(session).add(category)
    return category


def _a_transaction(
    owner_id: UUID,
    account: TargetAccount,
    category: Category,
    *,
    amount: str = "1500.00",
    day: int = 18,
    description: str = "Coto",
) -> Transaction:
    draft = Draft(
        kind=category.kind,
        money=Money(Decimal(amount), account.currency),
        category=category,
        occurred_on=date(2026, 9, day),
        description=Description.parse(description),
    )
    return register(draft, account, transaction_id=uuid4(), owner_id=owner_id, at=NOW)


async def test_a_saved_movement_comes_back_the_same(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    category = await _category(session, owner_id)
    repository = SqlAlchemyTransactionRepository(session)
    movement = _a_transaction(owner_id, account, category, amount="15300.50")

    await repository.add(movement)

    assert await repository.get(movement.id, owner_id) == movement


async def test_no_reading_brings_back_a_deleted_movement(session: AsyncSession) -> None:
    """La red que sostiene el borrado lógico (ADR-0011): si una lectura nueva se
    olvida de filtrar, este test falla."""
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    category = await _category(session, owner_id)
    repository = SqlAlchemyTransactionRepository(session)
    movement = _a_transaction(owner_id, account, category, amount="1000.00")
    await repository.add(movement)

    await repository.save(movement.deleted(NOW))

    page = await repository.page_for_owner(owner_id, TransactionFilters(), cursor=None, limit=50)
    assert page.items == []
    assert await repository.balances_for_owner(owner_id) == []
    assert await repository.count_by_category(category.id, owner_id) == 0
    # Solo `get` lo sigue viendo, que es lo que permite deshacer.
    found = await repository.get(movement.id, owner_id)
    assert found is not None
    assert found.is_deleted


async def test_the_balance_is_the_sum_of_the_movements(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    expenses = await _category(session, owner_id)
    incomes = await _category(session, owner_id, TransactionKind.INCOME, "Sueldo")
    repository = SqlAlchemyTransactionRepository(session)

    await repository.add(_a_transaction(owner_id, account, incomes, amount="100000.00"))
    await repository.add(_a_transaction(owner_id, account, expenses, amount="15300.50"))

    balances = await repository.balances_for_owner(owner_id)

    assert len(balances) == 1
    assert balances[0].account_id == account.id
    assert balances[0].balance == Money(Decimal("84699.50"), Currency.ARS)


async def test_the_pages_do_not_repeat_or_skip_rows(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    category = await _category(session, owner_id)
    repository = SqlAlchemyTransactionRepository(session)
    # Dos el mismo día, para que el desempate por identificador tenga que trabajar.
    for day in (15, 16, 17, 17):
        await repository.add(_a_transaction(owner_id, account, category, day=day))

    first = await repository.page_for_owner(owner_id, TransactionFilters(), cursor=None, limit=2)
    second = await repository.page_for_owner(
        owner_id, TransactionFilters(), cursor=first.next_cursor, limit=2
    )

    seen = [row.id for row in first.items + second.items]
    assert len(set(seen)) == 4
    assert [row.occurred_on.day for row in first.items] == [17, 17]
    assert second.next_cursor is None


async def test_nobody_reads_the_movements_of_another_person(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    stranger_id = await _user(session, "otra")
    account = await _account(session, owner_id)
    category = await _category(session, owner_id)
    repository = SqlAlchemyTransactionRepository(session)
    movement = _a_transaction(owner_id, account, category)
    await repository.add(movement)

    assert await repository.get(movement.id, stranger_id) is None
    page = await repository.page_for_owner(stranger_id, TransactionFilters(), cursor=None, limit=50)
    assert page.items == []
    assert await repository.balances_for_owner(stranger_id) == []


async def test_the_database_rejects_a_movement_in_another_currency(session: AsyncSession) -> None:
    """La regla vive también en la base: la clave foránea ata la moneda a la cuenta."""
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id, Currency.ARS)
    category = await _category(session, owner_id)

    with pytest.raises(IntegrityError):
        await session.execute(
            insert(transactions).values(
                id=uuid4(),
                owner_id=owner_id,
                account_id=account.id,
                currency="USD",
                kind="expense",
                amount=Decimal("10.00"),
                category_id=category.id,
                occurred_on=date(2026, 9, 18),
                created_at=NOW,
                updated_at=NOW,
            )
        )


async def test_the_database_rejects_an_income_with_an_expense_category(
    session: AsyncSession,
) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    expenses = await _category(session, owner_id)

    with pytest.raises(IntegrityError):
        await session.execute(
            insert(transactions).values(
                id=uuid4(),
                owner_id=owner_id,
                account_id=account.id,
                currency="ARS",
                kind="income",
                amount=Decimal("10.00"),
                category_id=expenses.id,
                occurred_on=date(2026, 9, 18),
                created_at=NOW,
                updated_at=NOW,
            )
        )


@pytest.mark.parametrize(
    ("amount", "currency"),
    [(Decimal("-1.00"), "ARS"), (Decimal("0.00"), "ARS"), (Decimal("10.999"), "ARS")],
)
async def test_the_database_rejects_amounts_that_do_not_fit(
    session: AsyncSession, amount: Decimal, currency: str
) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id, Currency(currency))
    category = await _category(session, owner_id)

    with pytest.raises(IntegrityError):
        await session.execute(
            insert(transactions).values(
                id=uuid4(),
                owner_id=owner_id,
                account_id=account.id,
                currency=currency,
                kind="expense",
                amount=amount,
                category_id=category.id,
                occurred_on=date(2026, 9, 18),
                created_at=NOW,
                updated_at=NOW,
            )
        )


async def test_the_audit_log_only_accepts_inserts(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    category = await _category(session, owner_id)
    movement = _a_transaction(owner_id, account, category)
    await SqlAlchemyTransactionRepository(session).add(movement)
    await SqlAlchemyAuditLog(session).record(AuditAction.REGISTERED, movement, NOW)

    entry = (
        (
            await session.execute(
                select(transaction_audit).where(transaction_audit.c.transaction_id == movement.id)
            )
        )
        .mappings()
        .one()
    )
    assert entry["action"] == "registered"
    assert entry["snapshot"]["amount"] == "1500.00"

    # Cada intento va en su propio punto de retorno: al fallar se deshace solo él,
    # y la fila de auditoría sigue ahí para el intento siguiente.
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            await session.execute(
                update(transaction_audit)
                .where(transaction_audit.c.id == entry["id"])
                .values(action="edited")
            )
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            await session.execute(
                text("DELETE FROM transaction_audit WHERE id = :id"), {"id": entry["id"]}
            )

    still_there = await session.execute(
        select(transaction_audit).where(transaction_audit.c.id == entry["id"])
    )
    assert still_there.mappings().one()["action"] == "registered"


async def test_the_same_seeds_are_not_planted_twice(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    repository = SqlAlchemyCategoryRepository(session)
    seeds = [
        Category(
            id=uuid4(),
            owner_id=owner_id,
            name=CategoryName.parse("Supermercado"),
            kind=TransactionKind.EXPENSE,
            created_at=NOW,
            slug="supermercado",
        )
    ]

    await repository.add_seeds(seeds)
    # Otra siembra simultánea: el mismo identificador sembrado, otra fila.
    await repository.add_seeds([replace(seeds[0], id=uuid4())])

    assert len(await repository.list_for_owner(owner_id)) == 1


async def test_an_idempotency_key_remembers_its_movement(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    category = await _category(session, owner_id)
    movement = _a_transaction(owner_id, account, category)
    await SqlAlchemyTransactionRepository(session).add(movement)
    store = SqlAlchemyIdempotencyStore(session)

    recordada = RememberedKey("huella", IdempotentResource.TRANSACTION, movement.id)

    await store.remember(owner_id, "clave-1", recordada, NOW)

    assert await store.recall(owner_id, "clave-1") == recordada
    assert await store.recall(owner_id, "otra") is None

    await store.forget_expired(NOW + timedelta(days=1))
    assert await store.recall(owner_id, "clave-1") is None


class TestBuscarPorTexto:
    """La búsqueda contra PostgreSQL real: el plegado y los comodines de LIKE."""

    async def _con_descripciones(
        self, session: AsyncSession, *descripciones: str
    ) -> tuple[UUID, SqlAlchemyTransactionRepository, list[Transaction]]:
        owner_id = await _user(session, "mechi")
        account = await _account(session, owner_id)
        category = await _category(session, owner_id)
        repository = SqlAlchemyTransactionRepository(session)
        filas = []
        for dia, descripcion in enumerate(descripciones, start=10):
            movimiento = _a_transaction(
                owner_id, account, category, day=dia, description=descripcion
            )
            await repository.add(movimiento)
            filas.append(movimiento)
        return owner_id, repository, filas

    async def _buscar(
        self, repository: SqlAlchemyTransactionRepository, owner_id: UUID, texto: str
    ) -> list[str]:
        page = await repository.page_for_owner(
            owner_id, TransactionFilters(text=texto), cursor=None, limit=50
        )
        return [row.description.value if row.description else "" for row in page.items]

    async def test_encuentra_sin_tildes_ni_mayusculas(self, session: AsyncSession) -> None:
        owner_id, repository, _ = await self._con_descripciones(
            session, "Panadería del barrio", "Verdulería"
        )

        assert await self._buscar(repository, owner_id, "PANADERIA") == ["Panadería del barrio"]

    async def test_encuentra_una_parte_del_texto(self, session: AsyncSession) -> None:
        owner_id, repository, _ = await self._con_descripciones(
            session, "Asado con los del trabajo"
        )

        assert await self._buscar(repository, owner_id, "los del") == ["Asado con los del trabajo"]

    async def test_el_comodin_de_like_se_busca_como_texto(self, session: AsyncSession) -> None:
        """Sin escapar, "%" traería todo y el filtro no filtraría nada."""
        owner_id, repository, _ = await self._con_descripciones(
            session, "Descuento 50% en la farmacia", "Café"
        )

        assert await self._buscar(repository, owner_id, "50%") == ["Descuento 50% en la farmacia"]
        assert await self._buscar(repository, owner_id, "%") == ["Descuento 50% en la farmacia"]

    async def test_el_guion_bajo_tampoco_es_comodin(self, session: AsyncSession) -> None:
        owner_id, repository, _ = await self._con_descripciones(session, "pago_mensual", "pagos")

        assert await self._buscar(repository, owner_id, "pago_") == ["pago_mensual"]

    async def test_sin_coincidencias_no_devuelve_nada(self, session: AsyncSession) -> None:
        owner_id, repository, _ = await self._con_descripciones(session, "Panadería")

        assert await self._buscar(repository, owner_id, "ferretería") == []

    async def test_filtra_por_categoria(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        account = await _account(session, owner_id)
        comida = await _category(session, owner_id, name="Comida")
        transporte = await _category(session, owner_id, name="Transporte")
        repository = SqlAlchemyTransactionRepository(session)
        await repository.add(_a_transaction(owner_id, account, comida, description="Coto"))
        await repository.add(_a_transaction(owner_id, account, transporte, description="Subte"))

        page = await repository.page_for_owner(
            owner_id, TransactionFilters(category_id=comida.id), cursor=None, limit=50
        )

        assert [row.description.value if row.description else "" for row in page.items] == ["Coto"]


SEPTEMBER = LedgerScope(since=date(2026, 9, 10), until=date(2026, 9, 20))


async def test_flow_totals_add_up_by_day_category_and_currency(session: AsyncSession) -> None:
    """La base suma: llega una fila por día y categoría, no una por movimiento (ADR-0018)."""
    owner_id = await _user(session, "mechi")
    pesos = await _account(session, owner_id)
    dollars = await _account(session, owner_id, Currency.USD)
    food = await _category(session, owner_id)
    salary = await _category(session, owner_id, TransactionKind.INCOME, "Sueldo")
    repository = SqlAlchemyTransactionRepository(session)
    for movement in (
        _a_transaction(owner_id, pesos, food, amount="100.25", day=12),
        _a_transaction(owner_id, pesos, food, amount="0.75", day=12),
        _a_transaction(owner_id, dollars, food, amount="3.00", day=12),
        _a_transaction(owner_id, pesos, salary, amount="9000.00", day=15),
        _a_transaction(owner_id, pesos, food, amount="5.00", day=9),
    ):
        await repository.add(movement)
    gone = _a_transaction(owner_id, pesos, food, amount="777.00", day=12)
    await repository.add(gone)
    await repository.save(gone.deleted(NOW))

    flows = await repository.flow_sums(owner_id, SEPTEMBER)
    names = {food.id: "Supermercado", salary.id: "Sueldo"}

    assert sorted((f.day.day, f.kind, names[f.category_id], f.total.amount, f.total.currency)
                  for f in flows) == [
        (12, TransactionKind.EXPENSE, "Supermercado", Decimal("3.00"), Currency.USD),
        (12, TransactionKind.EXPENSE, "Supermercado", Decimal("101.00"), Currency.ARS),
        (15, TransactionKind.INCOME, "Sueldo", Decimal("9000.00"), Currency.ARS),
    ]  # fmt: skip
    assert await repository.flow_sums(await _user(session, "otra"), SEPTEMBER) == []


async def test_flow_totals_only_for_the_chosen_accounts(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    one = await _account(session, owner_id)
    other = await _account(session, owner_id)
    food = await _category(session, owner_id)
    repository = SqlAlchemyTransactionRepository(session)
    await repository.add(_a_transaction(owner_id, one, food, amount="1.00", day=12))
    await repository.add(_a_transaction(owner_id, other, food, amount="2.00", day=12))

    flows = await repository.flow_sums(
        owner_id, LedgerScope(SEPTEMBER.since, SEPTEMBER.until, frozenset({one.id}))
    )

    assert [f.total for f in flows] == [Money(Decimal("1.00"), Currency.ARS)]


async def test_balance_changes_start_with_everything_before_the_period(
    session: AsyncSession,
) -> None:
    owner_id = await _user(session, "mechi")
    account = await _account(session, owner_id)
    food = await _category(session, owner_id)
    salary = await _category(session, owner_id, TransactionKind.INCOME, "Sueldo")
    repository = SqlAlchemyTransactionRepository(session)
    for movement in (
        _a_transaction(owner_id, account, salary, amount="1000.00", day=1),
        _a_transaction(owner_id, account, food, amount="100.00", day=9),
        _a_transaction(owner_id, account, food, amount="10.00", day=12),
        _a_transaction(owner_id, account, food, amount="5.00", day=12),
        # Después del período: no cuenta.
        _a_transaction(owner_id, account, food, amount="1.00", day=17),
    ):
        await repository.add(movement)

    changes = await repository.balance_changes(
        owner_id, LedgerScope(since=date(2026, 9, 10), until=date(2026, 9, 15))
    )

    assert sorted(changes, key=lambda c: c.month or date.min) == [
        BalanceChange(account.id, None, Money(Decimal("900.00"), Currency.ARS)),
        BalanceChange(account.id, date(2026, 9, 1), Money(Decimal("-15.00"), Currency.ARS)),
    ]


async def test_flows_in_the_reference_currency_are_added_by_month(session: AsyncSession) -> None:
    owner_id = await _user(session, "mechi")
    pesos = await _account(session, owner_id)
    dollars = await _account(session, owner_id, Currency.USD)
    food = await _category(session, owner_id)
    repository = SqlAlchemyTransactionRepository(session)
    for movement in (
        _a_transaction(owner_id, pesos, food, amount="1.00", day=11),
        _a_transaction(owner_id, pesos, food, amount="2.00", day=12),
        _a_transaction(owner_id, dollars, food, amount="3.00", day=11),
        _a_transaction(owner_id, dollars, food, amount="4.00", day=12),
    ):
        await repository.add(movement)

    flows = await repository.flow_sums(
        owner_id, LedgerScope(SEPTEMBER.since, SEPTEMBER.until, monthly_currency=Currency.ARS)
    )

    assert sorted((f.total.currency, f.day, f.total.amount) for f in flows) == [
        (Currency.ARS, date(2026, 9, 1), Decimal("3.00")),
        (Currency.USD, date(2026, 9, 11), Decimal("3.00")),
        (Currency.USD, date(2026, 9, 12), Decimal("4.00")),
    ]


class TestImportados:
    """La huella de importación (ADR-0023)."""

    async def test_la_huella_se_guarda_y_vuelve(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        account = await _account(session, owner_id)
        category = await _category(session, owner_id)
        repository = SqlAlchemyTransactionRepository(session)
        movement = replace(_a_transaction(owner_id, account, category), source_fingerprint="a" * 64)

        await repository.add(movement)

        assert await repository.get(movement.id, owner_id) == movement

    async def test_las_huellas_incluyen_los_borrados_y_son_del_dueno(
        self, session: AsyncSession
    ) -> None:
        owner_id = await _user(session, "mechi")
        stranger = await _user(session, "otra")
        account = await _account(session, owner_id)
        category = await _category(session, owner_id)
        repository = SqlAlchemyTransactionRepository(session)
        movement = replace(_a_transaction(owner_id, account, category), source_fingerprint="a" * 64)
        await repository.add(movement)
        await repository.save(movement.deleted(NOW))

        assert await repository.imported_fingerprints(
            owner_id, account.id, ["a" * 64, "b" * 64]
        ) == {"a" * 64}
        assert await repository.imported_fingerprints(stranger, account.id, ["a" * 64]) == set()
        assert await repository.imported_fingerprints(owner_id, account.id, []) == set()

    async def test_la_misma_huella_dos_veces_en_una_cuenta_es_un_conflicto(
        self, session: AsyncSession
    ) -> None:
        owner_id = await _user(session, "mechi")
        account = await _account(session, owner_id)
        other = await _account(session, owner_id)
        category = await _category(session, owner_id)
        repository = SqlAlchemyTransactionRepository(session)
        first = replace(_a_transaction(owner_id, account, category), source_fingerprint="a" * 64)
        await repository.add(first)
        # En otra cuenta la misma línea es otra cosa: puede ser el mismo archivo
        # importado por error en la cuenta equivocada.
        await repository.add(
            replace(_a_transaction(owner_id, other, category), source_fingerprint="a" * 64)
        )

        with pytest.raises(TransactionAlreadyImportedError):
            async with session.begin_nested():
                await repository.add(
                    replace(
                        _a_transaction(owner_id, account, category), source_fingerprint="a" * 64
                    )
                )

    async def test_la_base_solo_acepta_un_sha256(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        account = await _account(session, owner_id)
        category = await _category(session, owner_id)
        movement = replace(_a_transaction(owner_id, account, category), source_fingerprint="xyz")

        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await SqlAlchemyTransactionRepository(session).add(movement)

    async def test_los_de_una_cuenta_entre_dos_fechas(self, session: AsyncSession) -> None:
        owner_id = await _user(session, "mechi")
        account = await _account(session, owner_id)
        other = await _account(session, owner_id)
        category = await _category(session, owner_id)
        repository = SqlAlchemyTransactionRepository(session)
        inside = _a_transaction(owner_id, account, category, day=10)
        border = _a_transaction(owner_id, account, category, day=12)
        outside = _a_transaction(owner_id, account, category, day=13)
        elsewhere = _a_transaction(owner_id, other, category, day=11)
        deleted = _a_transaction(owner_id, account, category, day=11)
        for movement in (inside, border, outside, elsewhere, deleted):
            await repository.add(movement)
        await repository.save(deleted.deleted(NOW))

        found = await repository.in_account_between(
            owner_id, account.id, date(2026, 9, 10), date(2026, 9, 12)
        )

        assert {movement.id for movement in found} == {inside.id, border.id}
