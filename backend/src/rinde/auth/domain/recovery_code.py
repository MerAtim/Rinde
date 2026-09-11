"""Código de recuperación: 20 símbolos Crockford Base32 (100 bits), en 5 grupos de 4."""

from rinde.auth.domain.errors import InvalidRecoveryCodeError

# Sin I, L, O ni U: no se confunden con 1 y 0 al copiarlo a mano.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LENGTH = 20
_GROUP_SIZE = 4
_AMBIGUOUS = str.maketrans({"I": "1", "L": "1", "O": "0"})


def format_recovery_code(symbols: str) -> str:
    return "-".join(symbols[i : i + _GROUP_SIZE] for i in range(0, len(symbols), _GROUP_SIZE))


def normalize_recovery_code(raw: str) -> str:
    """Acepta minúsculas, espacios y guiones; I y L valen 1, O vale 0, como define Crockford."""
    cleaned = raw.upper().replace("-", "").replace(" ", "").translate(_AMBIGUOUS)
    if len(cleaned) != LENGTH or any(symbol not in ALPHABET for symbol in cleaned):
        raise InvalidRecoveryCodeError
    return cleaned
