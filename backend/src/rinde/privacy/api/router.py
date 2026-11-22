"""Endpoint de la exportación de los datos (Ley 25.326, art. 14; ADR-0034).

Solo lectura, así que no pide el encabezado CSRF, como el dashboard. No hay
identificador en el camino: se exporta a la persona de la sesión. No pide la
contraseña otra vez: con la sesión ya se puede leer todo por los otros
endpoints, así que pedirla acá no protegería nada más.
"""

from fastapi import APIRouter, Request, Response

from rinde.privacy.api.schemas import PersonalDataResponse
from rinde.privacy.application.use_cases import ExportPersonalData
from rinde.shared.api.identity import CurrentUserId
from rinde.shared.api.schemas import error_responses
from rinde.shared.domain.calendar import argentine_day

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.get("/export", responses=error_responses(401), summary="Descargar todos mis datos")
async def export_personal_data(
    request: Request, response: Response, user_id: CurrentUserId
) -> PersonalDataResponse:
    """Todo lo que Rinde guarda de la persona, en un JSON, como archivo para descargar.

    Incluye lo borrado que todavía se guarda y el historial de cambios. Nunca
    los hashes de la contraseña ni del código de recuperación.
    """
    export: ExportPersonalData = request.app.state.privacy_export
    data = await export.execute(user_id)
    day = argentine_day(data.generated_at)
    response.headers["Content-Disposition"] = (
        f'attachment; filename="rinde-datos-{day.isoformat()}.json"'
    )
    # Tiene todos los datos de la persona: ningún navegador ni intermediario lo guarda.
    response.headers["Cache-Control"] = "no-store"
    return PersonalDataResponse.from_data(data)
