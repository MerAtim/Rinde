import hashlib

import httpx
import pytest
from argon2 import PasswordHasher

from rinde.auth.infrastructure.argon2_hasher import Argon2PasswordHasher
from rinde.auth.infrastructure.pwned_passwords import PwnedPasswordsChecker

pytestmark = pytest.mark.anyio

PASSPHRASE = "mi gato come fideos los martes"


async def test_argon2_uses_the_owasp_parameters_and_verifies() -> None:
    hasher = Argon2PasswordHasher()

    secret_hash = await hasher.hash(PASSPHRASE)

    assert secret_hash.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert await hasher.verify(secret_hash, PASSPHRASE)
    assert not await hasher.verify(secret_hash, "otra frase cualquiera")
    assert not await hasher.verify("esto no es un hash", PASSPHRASE)
    assert not hasher.needs_rehash(secret_hash)
    weaker = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(PASSPHRASE)
    assert hasher.needs_rehash(weaker)


def _digest(password: str) -> str:
    return hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()


async def test_pwned_passwords_sends_only_the_prefix_and_detects_matches() -> None:
    digest = _digest(PASSPHRASE)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text=f"{'F' * 35}:3\r\n{digest[5:]}:42\r\n")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await PwnedPasswordsChecker(client).is_compromised(PASSPHRASE)

    assert requests[0].url.path == f"/range/{digest[:5]}"
    assert requests[0].headers["Add-Padding"] == "true"
    assert digest[5:] not in str(requests[0].url)


async def test_pwned_passwords_ignores_padding_entries() -> None:
    digest = _digest(PASSPHRASE)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=f"{digest[5:]}:0\r\n")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert not await PwnedPasswordsChecker(client).is_compromised(PASSPHRASE)


async def test_pwned_passwords_fails_open_when_the_service_is_down() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert not await PwnedPasswordsChecker(client).is_compromised(PASSPHRASE)
