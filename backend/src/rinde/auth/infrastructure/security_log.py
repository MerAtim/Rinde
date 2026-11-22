"""Adaptador del registro de seguridad de auth sobre el registro compartido (ADR-0035)."""

from rinde.auth.application.ports import SecurityEvent, SecurityParam
from rinde.shared.infrastructure.security_log import Level, record_security_event

# Los niveles son los que asigna el OWASP Logging Vocabulary a cada evento.
# Un test verifica que cada evento del puerto tiene su entrada.
CATALOG: dict[SecurityEvent, tuple[Level, str]] = {
    SecurityEvent.LOGIN_SUCCEEDED: (Level.INFO, "Inicio de sesión correcto"),
    SecurityEvent.LOGIN_FAILED: (Level.WARN, "Inicio de sesión fallido"),
    SecurityEvent.ACCOUNT_LOCKED: (
        Level.WARN,
        "Cuenta bloqueada por demasiados intentos fallidos: se rechazó el pedido",
    ),
    SecurityEvent.REAUTHENTICATION_FAILED: (
        Level.WARN,
        "Contraseña incorrecta al confirmar el borrado de la cuenta",
    ),
    SecurityEvent.PASSWORD_CHANGED: (
        Level.INFO,
        "Contraseña cambiada con el código de recuperación; se cerraron todas las sesiones",
    ),
    SecurityEvent.PASSWORD_CHANGE_FAILED: (
        Level.CRITICAL,
        "Código de recuperación incorrecto",
    ),
    SecurityEvent.RATE_LIMIT_EXCEEDED: (
        Level.WARN,
        "Tope de pedidos por dirección de origen alcanzado: se rechazó el pedido",
    ),
    SecurityEvent.SESSION_ENDED: (Level.INFO, "Sesión cerrada"),
    # El vocabulario le pone CRITICAL. Acá la sesión vence sola a los 30 días,
    # así que lo común es alguien que vuelve después de un tiempo, no un ataque:
    # con CRITICAL, el nivel que tiene que despertar a alguien perdería sentido.
    SecurityEvent.SESSION_USED_AFTER_EXPIRY: (
        Level.WARN,
        "Se usó una sesión vencida",
    ),
    SecurityEvent.USER_CREATED: (Level.WARN, "Cuenta creada"),
    SecurityEvent.USER_DELETED: (Level.WARN, "Cuenta borrada con todos sus datos"),
}


class LoggingSecurityLog:
    def record(
        self, event: SecurityEvent, *params: SecurityParam, client: str | None = None
    ) -> None:
        level, description = CATALOG[event]
        record_security_event(
            event.value,
            [str(param) for param in params],
            level=level,
            description=description,
            source_ip=client,
        )
