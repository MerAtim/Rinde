"""Repositorio de cotizaciones contra PostgreSQL real. Cada test se deshace al terminar."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from rinde.rates.domain.quote import ALL_RATE_TYPES, Quote, RateSource, RateType
from rinde.rates.infrastructure.repositories import SqlAlchemyQuoteRepository
from rinde.rates.infrastructure.tables import exchange_rates

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

DAY = date(2026, 3, 2)
FETCHED_AT = datetime(2026, 11, 10, 15, tzinfo=UTC)


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


def _quote(
    rate_type: RateType = RateType.MEP,
    *,
    source: RateSource = RateSource.ARGENTINADATOS,
    sell: str = "1210.12345678",
) -> Quote:
    return Quote(
        rate_type=rate_type,
        day=DAY,
        buy=Decimal("1190.5"),
        sell=Decimal(sell),
        source=source,
        updated_at=datetime(2026, 3, 2, 18, tzinfo=UTC),
    )


async def test_a_quote_comes_back_exactly_as_it_was_stored(session: AsyncSession) -> None:
    repository = SqlAlchemyQuoteRepository(session)

    await repository.add_all([_quote()], FETCHED_AT)

    assert await repository.for_day(DAY, ALL_RATE_TYPES) == [_quote()]


async def test_only_the_asked_types_and_day_are_returned(session: AsyncSession) -> None:
    repository = SqlAlchemyQuoteRepository(session)
    await repository.add_all([_quote(RateType.MEP), _quote(RateType.BLUE)], FETCHED_AT)

    assert [q.rate_type for q in await repository.for_day(DAY, frozenset({RateType.BLUE}))] == [
        RateType.BLUE
    ]
    assert await repository.for_day(date(2026, 3, 3), ALL_RATE_TYPES) == []
    assert await repository.for_day(DAY, frozenset()) == []


async def test_a_stored_quote_is_never_overwritten(session: AsyncSession) -> None:
    """Un día cerrado no cambia: si dos pedidos traen lo mismo, queda el primero."""
    repository = SqlAlchemyQuoteRepository(session)

    await repository.add_all([_quote(sell="1210")], FETCHED_AT)
    await repository.add_all([_quote(sell="9999")], FETCHED_AT)

    assert [q.sell for q in await repository.for_day(DAY, ALL_RATE_TYPES)] == [Decimal(1210)]


async def test_with_two_sources_for_one_day_the_chain_priority_wins(
    session: AsyncSession,
) -> None:
    repository = SqlAlchemyQuoteRepository(session)

    await repository.add_all(
        [_quote(source=RateSource.CRIPTOYA, sell="1300"), _quote(source=RateSource.DOLARAPI)],
        FETCHED_AT,
    )

    assert [q.source for q in await repository.for_day(DAY, ALL_RATE_TYPES)] == [
        RateSource.DOLARAPI
    ]


@pytest.mark.parametrize(
    "fields",
    [
        {"buy": Decimal(0)},
        {"buy": Decimal(1300), "sell": Decimal(1200)},
        {"base": "ARS"},
        {"base": "EUR"},
        {"rate_type": "mayorista"},
        {"source": "bcra"},
    ],
)
async def test_the_database_rejects_an_impossible_row(
    session: AsyncSession, fields: dict[str, Any]
) -> None:
    row = {
        "day": DAY,
        "base": "USD",
        "counter": "ARS",
        "rate_type": "mep",
        "source": "argentinadatos",
        "buy": Decimal(1190),
        "sell": Decimal(1210),
        "fetched_at": FETCHED_AT,
        **fields,
    }

    with pytest.raises(IntegrityError):
        await session.execute(insert(exchange_rates).values(row))
