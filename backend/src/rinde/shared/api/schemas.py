"""Esquemas web compartidos por todos los módulos."""

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Toda respuesta de error: un código estable, nunca un mensaje traducido ni una traza."""

    code: str


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Documenta en OpenAPI qué códigos de error puede devolver un endpoint."""
    return {code: {"model": ErrorResponse} for code in status_codes}
