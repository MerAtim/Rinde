"""Límites por dirección de origen.

El límite por cuenta (NIST SP 800-63B-4) no ve el rociado de contraseñas: el
ataque prueba una contraseña común contra miles de cuentas, así que cada cuenta
falla una sola vez y ninguna llega a su tope. Lo que esos intentos comparten es
el origen, y eso es lo que cuentan estos límites.

Los topes son más altos que el de cada cuenta a propósito: detrás de una misma
dirección puede haber muchas personas (una oficina, la red de un celular).
"""

from datetime import timedelta

from rinde.auth.application.dependencies import AuthDependencies
from rinde.auth.application.ports import ClientAction
from rinde.auth.domain.errors import TooManyAttemptsError

MAX_FAILURES_PER_CLIENT = 30
FAILURE_WINDOW = timedelta(minutes=15)

MAX_REGISTRATIONS_PER_CLIENT = 5
REGISTRATION_WINDOW = timedelta(hours=1)

# Más allá de la ventana más larga, una fila ya no cuenta para nada.
RETENTION = max(FAILURE_WINDOW, REGISTRATION_WINDOW)

_LIMITS = {
    ClientAction.LOGIN_FAILURE: (MAX_FAILURES_PER_CLIENT, FAILURE_WINDOW),
    ClientAction.REGISTRATION: (MAX_REGISTRATIONS_PER_CLIENT, REGISTRATION_WINDOW),
}


async def ensure_client_under_limit(
    deps: AuthDependencies, action: ClientAction, client: str | None
) -> None:
    """Falla abierto si no se conoce el origen.

    Sin dirección no hay a quién contarle los intentos, y meterlos todos en una
    misma bolsa dejaría a cualquiera bloquear a todos los demás. El límite por
    cuenta sigue en pie de todos modos.
    """
    if client is None:
        return
    limit, window = _LIMITS[action]
    since = deps.services.clock.now() - window
    if await deps.client_activity.count_since(action, client, since) >= limit:
        raise TooManyAttemptsError(retry_after_seconds=int(window.total_seconds()))


async def record_client_action(
    deps: AuthDependencies, action: ClientAction, client: str | None
) -> None:
    """Registra la acción y aprovecha el paso para limpiar lo que ya venció.

    La limpieza va acá y no en una tarea programada porque el plan gratuito de
    Render no tiene programador de tareas. Como se limpia en cada escritura, la
    tabla no crece y los datos de origen no se guardan más de lo necesario.
    """
    if client is None:
        return
    now = deps.services.clock.now()
    await deps.client_activity.record(action, client, now)
    await deps.client_activity.purge_before(now - RETENTION)
