"""Registro de eventos de seguridad (ADR-0035, OWASP Top 10 A09).

Cada evento es una línea JSON en la salida estándar, que Render recoge y guarda.
Los nombres siguen el OWASP Logging Vocabulary (`authn_login_fail:<id>`), así
quien lee el registro no necesita un diccionario propio de Rinde.

Qué nunca entra, por diseño y no por cuidado de quien llama:

* El nombre de usuario: alguien puede escribir su contraseña en ese campo, y
  además es un dato personal que no hace falta (Ley 25.326, art. 4). Se usa el
  identificador interno de la cuenta, que no dice nada fuera de la base.
* Contraseñas, tokens, códigos de recuperación y hashes.
* Los parámetros de la consulta y el cuerpo del pedido.

Los campos de nivel superior salen de una lista cerrada y todo se serializa con
`json.dumps`, que escapa saltos de línea y caracteres de control: un valor que
viene de afuera, como la ruta, no puede inventar una línea de registro (CWE-117).
"""

import json
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import TextIO

LOGGER_NAME = "rinde.security"
APP_ID = "rinde.api"
MAX_URI_LENGTH = 256
"""Una ruta inventada por un escáner puede ser larguísima; se corta acá."""

_FIELDS = ("event", "level", "description", "source_ip", "request_method", "request_uri")
"""Lista cerrada de campos, con los nombres que recomienda el vocabulario de OWASP."""

logger = logging.getLogger(LOGGER_NAME)


class Level(StrEnum):
    """Los tres niveles que usa el vocabulario de OWASP."""

    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


_PYTHON_LEVELS = {
    Level.INFO: logging.INFO,
    Level.WARN: logging.WARNING,
    Level.CRITICAL: logging.CRITICAL,
}


def record_security_event(  # noqa: PLR0913  (cada campo del vocabulario es un parámetro con nombre)
    event: str,
    params: Sequence[str],
    *,
    level: Level,
    description: str,
    source_ip: str | None = None,
    request_method: str | None = None,
    request_uri: str | None = None,
) -> None:
    """Escribe un evento. `params` va pegado al nombre, como pide el vocabulario."""
    fields = {
        "event": f"{event}:{','.join(params)}" if params else event,
        "level": level.value,
        "description": description,
        "source_ip": source_ip,
        "request_method": request_method,
        "request_uri": request_uri[:MAX_URI_LENGTH] if request_uri else None,
    }
    present = {key: value for key, value in fields.items() if value is not None}
    logger.log(_PYTHON_LEVELS[level], description, extra={"security_event": present})


class SecurityEventFormatter(logging.Formatter):
    """Una línea JSON por evento, con la hora en UTC."""

    def format(self, record: logging.LogRecord) -> str:
        fields = getattr(record, "security_event", None)
        if not isinstance(fields, dict):
            # Alguien usó este logger sin pasar por record_security_event: se
            # registra igual, pero sin nada que no esté en la lista cerrada.
            fields = {"event": "unstructured", "level": record.levelname}
        line = {
            "datetime": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "appid": APP_ID,
            **{key: fields[key] for key in _FIELDS if key in fields},
        }
        return json.dumps(line, ensure_ascii=True, separators=(",", ":"))


class _SecurityHandler(logging.StreamHandler[TextIO]):
    """Marca propia para no agregar dos veces el mismo destino."""


def configure_security_log(stream: TextIO | None = None) -> None:
    """Manda los eventos a la salida estándar, una sola vez por proceso.

    No se propagan al logger raíz: así nadie les cambia el formato ni los manda
    a otro destino sin pasar por acá.
    """
    if any(isinstance(handler, _SecurityHandler) for handler in logger.handlers):
        return
    handler = _SecurityHandler(stream or sys.stdout)
    handler.setFormatter(SecurityEventFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
