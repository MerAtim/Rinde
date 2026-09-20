"""Endpoints de movimientos y categorías (ADR-0011).

Todos piden `CurrentUserId`: sin sesión responden 401. Los que cambian estado
exigen además el encabezado CSRF.
"""

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from rinde.shared.api.csrf import CSRF
from rinde.shared.api.identity import CurrentUserId
from rinde.shared.api.schemas import error_responses
from rinde.transactions.api.schemas import (
    BalanceResponse,
    CategoryRequest,
    CategoryResponse,
    EditTransactionRequest,
    HistoryPageResponse,
    RegisterTransactionRequest,
    RenameCategoryRequest,
    TransactionPageResponse,
    TransactionQuery,
    TransactionResponse,
    TransferPageResponse,
    TransferQuery,
    TransferRequest,
    TransferResponse,
)
from rinde.transactions.application.ports import TransactionFilters, TransferFilters
from rinde.transactions.application.unit import TransactionsUnit, TransactionsUnitFactory
from rinde.transactions.application.use_cases import TransactionInput, TransferInput

router = APIRouter(tags=["transactions"])


async def transactions_unit(request: Request) -> AsyncIterator[TransactionsUnit]:
    """Una unidad de trabajo por pedido: si algo falla, su transacción se descarta."""
    factory: TransactionsUnitFactory = request.app.state.transactions_factory
    async with factory() as unit:
        yield unit


Unit = Annotated[TransactionsUnit, Depends(transactions_unit)]
# Una clave por pedido, elegida por el cliente: sirve para reintentar sin duplicar.
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=255)]


@router.get("/transactions", responses=error_responses(401, 422), summary="Listar mis movimientos")
async def list_transactions(
    user_id: CurrentUserId, unit: Unit, query: Annotated[TransactionQuery, Query()]
) -> TransactionPageResponse:
    page = await unit.list.execute(
        user_id,
        TransactionFilters(account_id=query.account_id, since=query.since, until=query.until),
        cursor=query.cursor,
        limit=query.limit,
    )
    return TransactionPageResponse.from_page(page)


@router.get(
    "/history",
    responses=error_responses(401, 422),
    summary="Listar mis movimientos y transferencias juntos",
)
async def list_history(
    user_id: CurrentUserId, unit: Unit, query: Annotated[TransactionQuery, Query()]
) -> HistoryPageResponse:
    """La línea de tiempo completa.

    `/transactions` sigue devolviendo solo movimientos: es lo que necesita un
    reporte de gastos, donde una transferencia no tiene nada que hacer.
    """
    page = await unit.history.execute(
        user_id,
        TransactionFilters(account_id=query.account_id, since=query.since, until=query.until),
        cursor=query.cursor,
        limit=query.limit,
    )
    return HistoryPageResponse.from_page(page)


@router.get(
    "/transactions/balances",
    responses=error_responses(401),
    summary="Saldo de cada una de mis cuentas",
)
async def list_balances(user_id: CurrentUserId, unit: Unit) -> list[BalanceResponse]:
    balances = await unit.balances.execute(user_id)
    return [BalanceResponse.from_balance(balance) for balance in balances]


@router.post(
    "/transactions",
    status_code=status.HTTP_201_CREATED,
    dependencies=CSRF,
    responses=error_responses(401, 403, 404, 409, 422),
    summary="Registrar un movimiento",
)
async def register_transaction(
    payload: RegisterTransactionRequest,
    user_id: CurrentUserId,
    unit: Unit,
    idempotency_key: IdempotencyKey = None,
) -> TransactionResponse:
    transaction = await unit.register.execute(
        user_id,
        TransactionInput(
            account_id=payload.account_id,
            kind=payload.kind,
            amount=payload.amount,
            category_id=payload.category_id,
            occurred_on=payload.occurred_on,
            description=payload.description,
        ),
        idempotency_key,
    )
    return TransactionResponse.from_transaction(transaction)


@router.get(
    "/transactions/{transaction_id}",
    responses=error_responses(401, 404),
    summary="Ver un movimiento",
)
async def get_transaction(
    transaction_id: UUID, user_id: CurrentUserId, unit: Unit
) -> TransactionResponse:
    return TransactionResponse.from_transaction(await unit.get.execute(user_id, transaction_id))


@router.patch(
    "/transactions/{transaction_id}",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404, 422),
    summary="Editar un movimiento",
)
async def edit_transaction(
    transaction_id: UUID,
    payload: EditTransactionRequest,
    user_id: CurrentUserId,
    unit: Unit,
) -> TransactionResponse:
    existing = await unit.get.execute(user_id, transaction_id)
    transaction = await unit.edit.execute(
        user_id,
        transaction_id,
        TransactionInput(
            account_id=existing.account_id,
            kind=payload.kind,
            amount=payload.amount,
            category_id=payload.category_id,
            occurred_on=payload.occurred_on,
            description=payload.description,
        ),
    )
    return TransactionResponse.from_transaction(transaction)


@router.delete(
    "/transactions/{transaction_id}",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404),
    summary="Borrar un movimiento",
)
async def delete_transaction(
    transaction_id: UUID, user_id: CurrentUserId, unit: Unit
) -> TransactionResponse:
    """El borrado es lógico y se puede deshacer (ADR-0011)."""
    return TransactionResponse.from_transaction(await unit.delete.execute(user_id, transaction_id))


@router.post(
    "/transactions/{transaction_id}/restore",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404),
    summary="Deshacer el borrado de un movimiento",
)
async def restore_transaction(
    transaction_id: UUID, user_id: CurrentUserId, unit: Unit
) -> TransactionResponse:
    return TransactionResponse.from_transaction(await unit.restore.execute(user_id, transaction_id))


def _transfer_input(payload: TransferRequest) -> TransferInput:
    return TransferInput(
        from_account_id=payload.from_account_id,
        to_account_id=payload.to_account_id,
        sent=payload.sent,
        received=payload.received,
        occurred_on=payload.occurred_on,
        description=payload.description,
    )


@router.get("/transfers", responses=error_responses(401, 422), summary="Listar mis transferencias")
async def list_transfers(
    user_id: CurrentUserId, unit: Unit, query: Annotated[TransferQuery, Query()]
) -> TransferPageResponse:
    page = await unit.list_transfers.execute(
        user_id,
        TransferFilters(account_id=query.account_id, since=query.since, until=query.until),
        cursor=query.cursor,
        limit=query.limit,
    )
    return TransferPageResponse.from_page(page)


@router.post(
    "/transfers",
    status_code=status.HTTP_201_CREATED,
    dependencies=CSRF,
    responses=error_responses(401, 403, 404, 409, 422),
    summary="Registrar una transferencia entre dos cuentas propias",
)
async def register_transfer(
    payload: TransferRequest,
    user_id: CurrentUserId,
    unit: Unit,
    idempotency_key: IdempotencyKey = None,
) -> TransferResponse:
    transfer = await unit.register_transfer.execute(
        user_id, _transfer_input(payload), idempotency_key
    )
    return TransferResponse.from_transfer(transfer)


@router.get(
    "/transfers/{transfer_id}",
    responses=error_responses(401, 404),
    summary="Ver una transferencia",
)
async def get_transfer(transfer_id: UUID, user_id: CurrentUserId, unit: Unit) -> TransferResponse:
    return TransferResponse.from_transfer(await unit.get_transfer.execute(user_id, transfer_id))


@router.patch(
    "/transfers/{transfer_id}",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404, 409, 422),
    summary="Editar una transferencia",
)
async def edit_transfer(
    transfer_id: UUID, payload: TransferRequest, user_id: CurrentUserId, unit: Unit
) -> TransferResponse:
    """Las cuentas sí se editan: equivocarse de cuenta es el error más fácil acá."""
    transfer = await unit.edit_transfer.execute(user_id, transfer_id, _transfer_input(payload))
    return TransferResponse.from_transfer(transfer)


@router.delete(
    "/transfers/{transfer_id}",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404),
    summary="Borrar una transferencia",
)
async def delete_transfer(
    transfer_id: UUID, user_id: CurrentUserId, unit: Unit
) -> TransferResponse:
    """El borrado es lógico y se puede deshacer (ADR-0014, decisión 4)."""
    return TransferResponse.from_transfer(await unit.delete_transfer.execute(user_id, transfer_id))


@router.post(
    "/transfers/{transfer_id}/restore",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404),
    summary="Deshacer el borrado de una transferencia",
)
async def restore_transfer(
    transfer_id: UUID, user_id: CurrentUserId, unit: Unit
) -> TransferResponse:
    return TransferResponse.from_transfer(await unit.restore_transfer.execute(user_id, transfer_id))


@router.get("/categories", responses=error_responses(401), summary="Listar mis categorías")
async def list_categories(user_id: CurrentUserId, unit: Unit) -> list[CategoryResponse]:
    categories = await unit.categories.execute(user_id)
    return [CategoryResponse.from_category(category) for category in categories]


@router.post(
    "/categories",
    status_code=status.HTTP_201_CREATED,
    dependencies=CSRF,
    responses=error_responses(401, 403, 409, 422),
    summary="Crear una categoría",
)
async def create_category(
    payload: CategoryRequest, user_id: CurrentUserId, unit: Unit
) -> CategoryResponse:
    category = await unit.create_category.execute(user_id, payload.name, payload.kind)
    return CategoryResponse.from_category(category)


@router.patch(
    "/categories/{category_id}",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404, 409, 422),
    summary="Renombrar una categoría",
)
async def rename_category(
    category_id: UUID, payload: RenameCategoryRequest, user_id: CurrentUserId, unit: Unit
) -> CategoryResponse:
    category = await unit.rename_category.execute(user_id, category_id, payload.name)
    return CategoryResponse.from_category(category)


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=CSRF,
    responses=error_responses(401, 403, 404, 409),
    summary="Borrar una categoría sin movimientos",
)
async def delete_category(category_id: UUID, user_id: CurrentUserId, unit: Unit) -> Response:
    await unit.delete_category.execute(user_id, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
