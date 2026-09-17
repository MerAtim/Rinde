"""Endpoints de cuentas (ADR-0009).

Todos piden `CurrentUserId`: sin sesión responden 401. Los que cambian estado
exigen además el encabezado CSRF.
"""

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from rinde.accounts.api.schemas import AccountResponse, OpenAccountRequest, RenameAccountRequest
from rinde.accounts.application.unit import AccountsUnit, AccountsUnitFactory
from rinde.shared.api.csrf import CSRF
from rinde.shared.api.identity import CurrentUserId
from rinde.shared.api.schemas import error_responses

router = APIRouter(prefix="/accounts", tags=["accounts"])


async def accounts_unit(request: Request) -> AsyncIterator[AccountsUnit]:
    """Una unidad de trabajo por pedido: si algo falla, su transacción se descarta."""
    factory: AccountsUnitFactory = request.app.state.accounts_factory
    async with factory() as unit:
        yield unit


Unit = Annotated[AccountsUnit, Depends(accounts_unit)]


@router.get("", responses=error_responses(401), summary="Listar mis cuentas")
async def list_accounts(
    user_id: CurrentUserId, unit: Unit, include_archived: bool = False
) -> list[AccountResponse]:
    # Sin paginación a propósito: una persona tiene decenas de cuentas, no miles.
    accounts = await unit.list.execute(user_id, include_archived=include_archived)
    return [AccountResponse.from_account(account) for account in accounts]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=CSRF,
    responses=error_responses(401, 403, 422),
    summary="Abrir una cuenta",
)
async def open_account(
    payload: OpenAccountRequest, user_id: CurrentUserId, unit: Unit
) -> AccountResponse:
    account = await unit.open.execute(user_id, payload.name, payload.kind, payload.currency)
    return AccountResponse.from_account(account)


@router.get("/{account_id}", responses=error_responses(401, 404), summary="Ver una cuenta")
async def get_account(account_id: UUID, user_id: CurrentUserId, unit: Unit) -> AccountResponse:
    return AccountResponse.from_account(await unit.get.execute(user_id, account_id))


@router.patch(
    "/{account_id}",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404, 409, 422),
    summary="Renombrar una cuenta",
)
async def rename_account(
    account_id: UUID, payload: RenameAccountRequest, user_id: CurrentUserId, unit: Unit
) -> AccountResponse:
    account = await unit.rename.execute(user_id, account_id, payload.name)
    return AccountResponse.from_account(account)


@router.post(
    "/{account_id}/archive",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404),
    summary="Archivar una cuenta",
)
async def archive_account(account_id: UUID, user_id: CurrentUserId, unit: Unit) -> AccountResponse:
    return AccountResponse.from_account(await unit.archive.execute(user_id, account_id))
