"""Endpoints de importación (ADR-0023).

Subir un archivo crea un lote; la vista previa lo muestra; confirmar registra
las líneas elegidas. Un lote de otra persona responde 404, igual que uno que no
existe o que venció (ADR-0009).
"""

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile, status

from rinde.imports.api.schemas import (
    BatchResponse,
    ConfirmRequest,
    ConfirmResponse,
    CsvLayoutRequest,
)
from rinde.imports.application.unit import ImportsUnit, ImportsUnitFactory
from rinde.imports.domain.statement import MAX_BYTES
from rinde.shared.api.csrf import CSRF
from rinde.shared.api.identity import CurrentUserId
from rinde.shared.api.schemas import error_responses

router = APIRouter(prefix="/imports", tags=["imports"])

LAYOUT_LENGTH = 2000
"""El formato es un JSON chico: un campo más largo no es un formato."""


async def imports_unit(request: Request) -> AsyncIterator[ImportsUnit]:
    factory: ImportsUnitFactory = request.app.state.imports_factory
    async with factory() as unit:
        yield unit


Unit = Annotated[ImportsUnit, Depends(imports_unit)]


@router.post(
    "",
    dependencies=CSRF,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 403, 404, 409, 413, 422),
    summary="Subir un archivo y ver la vista previa",
)
async def create_import(
    user_id: CurrentUserId,
    unit: Unit,
    file: Annotated[UploadFile, File(description="CSV, hasta 1 MB y 2.000 líneas")],
    account_id: Annotated[UUID, Form()],
    layout: Annotated[str, Form(max_length=LAYOUT_LENGTH, description="CsvLayoutRequest en JSON")],
) -> BatchResponse:
    """El archivo no se guarda: se guarda lo que se leyó, su nombre y su huella."""
    reader = CsvLayoutRequest.parse(layout)
    # Uno más que el máximo: alcanza para saber que se pasó sin leer el resto.
    content = await file.read(MAX_BYTES + 1)
    preview = await unit.create.execute(
        user_id, account_id, file.filename or "archivo", content, reader
    )
    return BatchResponse.from_preview(preview)


@router.get(
    "/{batch_id}", responses=error_responses(401, 404), summary="Ver la vista previa de un lote"
)
async def get_import(batch_id: UUID, user_id: CurrentUserId, unit: Unit) -> BatchResponse:
    return BatchResponse.from_preview(await unit.get.execute(user_id, batch_id))


@router.post(
    "/{batch_id}/confirm",
    dependencies=CSRF,
    responses=error_responses(401, 403, 404, 409, 422),
    summary="Registrar las líneas elegidas",
)
async def confirm_import(
    batch_id: UUID, payload: ConfirmRequest, user_id: CurrentUserId, unit: Unit
) -> ConfirmResponse:
    """Confirmar otra vez el mismo lote devuelve lo mismo y no duplica nada."""
    confirmation = await unit.confirm.execute(user_id, batch_id, payload.choices())
    return ConfirmResponse.from_confirmation(confirmation)


@router.delete(
    "/{batch_id}",
    dependencies=CSRF,
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 403, 404),
    summary="Descartar un lote sin confirmar",
)
async def discard_import(batch_id: UUID, user_id: CurrentUserId, unit: Unit) -> Response:
    await unit.discard.execute(user_id, batch_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
