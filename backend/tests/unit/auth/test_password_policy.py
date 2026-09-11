import pytest

from rinde.auth.domain.errors import (
    PasswordContainsUsernameError,
    PasswordTooLongError,
    PasswordTooShortError,
    PasswordTooSimpleError,
)
from rinde.auth.domain.password_policy import check_password_policy
from rinde.auth.domain.username import Username

USER = Username.parse("mechi")


def test_accepts_a_long_passphrase_without_composition_rules() -> None:
    passphrase = "mi gato come fideos los martes"

    assert check_password_policy(passphrase, USER) == passphrase


def test_normalizes_unicode_before_counting() -> None:
    plain = "mi gato come fideos"
    # Letras de ancho completo, generadas a propósito: NFKC las vuelve a su forma común.
    fullwidth = "".join(char if char == " " else chr(ord(char) + 0xFEE0) for char in plain)

    assert check_password_policy(fullwidth, USER) == plain


def test_counts_characters_not_bytes() -> None:
    # 15 caracteres, más de 15 bytes por la ñ y la tilde.
    assert check_password_policy("ñandúes felices", USER) == "ñandúes felices"


@pytest.mark.parametrize(
    ("password", "error"),
    [
        ("corta pero no", PasswordTooShortError),
        ("frase " * 22, PasswordTooLongError),
        ("la cuenta de mechi es mía", PasswordContainsUsernameError),
        ("ababababababababab", PasswordTooSimpleError),
    ],
)
def test_rejects_passwords_outside_the_policy(password: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        check_password_policy(password, USER)
