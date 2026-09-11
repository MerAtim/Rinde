import pytest

from rinde.auth.domain.errors import UsernameInvalidError, UsernameReservedError
from rinde.auth.domain.username import Username


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("mechi", "mechi"),
        ("  Mechi.Dev ", "mechi.dev"),
        ("ana_2026", "ana_2026"),
        # Letras de ancho completo, generadas a propósito para probar la normalización.
        ("".join(chr(ord(char) + 0xFEE0) for char in "MECHI"), "mechi"),
    ],
)
def test_normalizes_valid_usernames(raw: str, expected: str) -> None:
    assert Username.parse(raw).value == expected


@pytest.mark.parametrize(
    "raw", ["", "ab", "a" * 31, ".mechi", "mechi-", "con espacio", "ñandú", "mechi😀"]
)
def test_rejects_invalid_usernames(raw: str) -> None:
    with pytest.raises(UsernameInvalidError):
        Username.parse(raw)


@pytest.mark.parametrize("raw", ["admin", "Rinde", "SOPORTE"])
def test_rejects_reserved_usernames(raw: str) -> None:
    with pytest.raises(UsernameReservedError):
        Username.parse(raw)
