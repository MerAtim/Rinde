"""Control de contraseñas filtradas con Pwned Passwords (k-anonimato)."""

import hashlib
import logging

import httpx

logger = logging.getLogger(__name__)


class PwnedPasswordsChecker:
    """Solo viajan los 5 primeros caracteres del SHA-1: el servicio nunca ve la contraseña.

    Si el servicio no responde, el control se omite y queda en el log (falla abierta,
    ADR-0007): se prioriza que la gente pueda registrarse.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str = "https://api.pwnedpasswords.com/range/",
        timeout_seconds: float = 2.0,
    ) -> None:
        self._client = client
        self._base_url = base_url
        self._timeout = timeout_seconds

    async def is_compromised(self, password: str) -> bool:
        digest = hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()
        prefix, suffix = digest[:5], digest[5:]
        try:
            response = await self._client.get(
                f"{self._base_url}{prefix}",
                headers={"Add-Padding": "true"},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            logger.warning("Pwned Passwords no respondió: se omite el control", exc_info=True)
            return False
        return _contains(response.text, suffix)


def _contains(body: str, suffix: str) -> bool:
    """La respuesta es de un tercero: se interpreta con cuidado. El relleno trae conteo 0."""
    for line in body.splitlines():
        candidate, _, count = line.strip().partition(":")
        if candidate == suffix and count.isdigit() and int(count) > 0:
            return True
    return False
