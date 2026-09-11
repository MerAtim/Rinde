import pytest

from rinde.auth.domain.errors import InvalidRecoveryCodeError
from rinde.auth.domain.recovery_code import format_recovery_code, normalize_recovery_code


def test_formats_in_five_groups_of_four() -> None:
    assert format_recovery_code("ABCD" * 5) == "ABCD-ABCD-ABCD-ABCD-ABCD"


def test_forgives_how_people_copy_it() -> None:
    assert normalize_recovery_code("abcd efgh-jkmn pqrs tvwx") == "ABCDEFGHJKMNPQRSTVWX"


def test_ambiguous_letters_count_as_digits() -> None:
    assert normalize_recovery_code("OIL0" + "1" * 16) == "0110" + "1" * 16


@pytest.mark.parametrize("raw", ["ABCD", "U" * 20, "ABCD-ABCD-ABCD-ABCD-ABC!"])
def test_rejects_malformed_codes(raw: str) -> None:
    with pytest.raises(InvalidRecoveryCodeError):
        normalize_recovery_code(raw)
