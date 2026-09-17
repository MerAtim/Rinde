"""Reglas de la cuenta (ADR-0009)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from rinde.accounts.domain.account import Account, AccountKind, AccountName
from rinde.accounts.domain.errors import (
    AccountArchivedError,
    AccountCurrencyNotAllowedError,
    AccountNameInvalidError,
)
from rinde.shared.domain.money import Currency

NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


def _account(kind: AccountKind = AccountKind.BANK, currency: Currency = Currency.ARS) -> Account:
    return Account(
        id=uuid4(),
        owner_id=uuid4(),
        name=AccountName.parse("Galicia sueldo"),
        kind=kind,
        currency=currency,
        created_at=NOW,
    )


def test_the_name_is_trimmed_and_normalized() -> None:
    # "Nación" con la tilde como carácter combinado, como la escriben algunos teclados.
    decomposed = "  Nación  "

    assert AccountName.parse(decomposed) == AccountName.parse("Nación")
    assert AccountName.parse(decomposed).value == "Nación"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "x" * 61,
        "Galicia\u200bsueldo",  # espacio de ancho cero: parece "Galiciasueldo"
        "Galicia\nsueldo",
    ],
)
def test_invalid_names_are_rejected(raw: str) -> None:
    with pytest.raises(AccountNameInvalidError):
        AccountName.parse(raw)


def test_sixty_characters_is_the_limit() -> None:
    assert len(AccountName.parse("x" * 60).value) == 60


@pytest.mark.parametrize("kind", [AccountKind.CASH, AccountKind.BANK, AccountKind.CREDIT_CARD])
def test_bitcoin_only_lives_in_crypto_wallets(kind: AccountKind) -> None:
    with pytest.raises(AccountCurrencyNotAllowedError):
        _account(kind=kind, currency=Currency.BTC)


@pytest.mark.parametrize("currency", list(Currency))
def test_a_crypto_wallet_accepts_any_currency(currency: Currency) -> None:
    assert _account(kind=AccountKind.CRYPTO_WALLET, currency=currency).currency is currency


def test_archiving_twice_keeps_the_first_date() -> None:
    archived = _account().archived(NOW)

    assert archived.archived(NOW + timedelta(days=3)).archived_at == NOW


def test_an_archived_account_cannot_be_renamed() -> None:
    archived = _account().archived(NOW)

    with pytest.raises(AccountArchivedError):
        archived.renamed(AccountName.parse("Otro nombre"))


def test_renaming_keeps_everything_else() -> None:
    account = _account()

    renamed = account.renamed(AccountName.parse("Galicia ahorro"))

    assert renamed.name.value == "Galicia ahorro"
    assert (renamed.id, renamed.currency, renamed.kind) == (
        account.id,
        account.currency,
        account.kind,
    )
