"""Endpoints de salud.

* liveness: el proceso está vivo (no consulta dependencias).
* readiness: la API puede atender pedidos (consulta la base de datos).
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel

from rinde.health.application.check_readiness import CheckReadiness

router = APIRouter(prefix="/health", tags=["health"])

type ComponentStatus = Literal["ok", "unavailable"]


class LivenessResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ReadinessResponse(BaseModel):
    status: ComponentStatus
    database: ComponentStatus


def get_check_readiness(request: Request) -> CheckReadiness:
    use_case = request.app.state.check_readiness
    if not isinstance(use_case, CheckReadiness):
        msg = "CheckReadiness no está configurado en app.state"
        raise TypeError(msg)
    return use_case


def get_version(request: Request) -> str:
    version = request.app.state.version
    if not isinstance(version, str):
        msg = "La versión no está configurada en app.state"
        raise TypeError(msg)
    return version


def _status(ok: bool) -> ComponentStatus:
    return "ok" if ok else "unavailable"


# HEAD se acepta para monitores de disponibilidad; no se publica en el contrato.
@router.head("/live", include_in_schema=False)
@router.get("/live", summary="El proceso está vivo y qué versión corre")
async def live(version: Annotated[str, Depends(get_version)]) -> LivenessResponse:
    return LivenessResponse(status="ok", version=version)


@router.head("/ready", include_in_schema=False)
@router.get(
    "/ready",
    summary="La API puede atender pedidos",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": "Alguna dependencia no está disponible",
        },
    },
)
async def ready(
    response: Response,
    check_readiness: Annotated[CheckReadiness, Depends(get_check_readiness)],
) -> ReadinessResponse:
    report = await check_readiness.execute()
    if not report.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status=_status(report.ready), database=_status(report.database))
