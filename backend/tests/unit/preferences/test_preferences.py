"""Preferencias: valores por defecto, cambios y lo que no se puede elegir."""

from datetime import timedelta
from uuid import uuid4

import pytest

from rinde.preferences.application.use_cases import (
    GetPreferences,
    PreferencesDependencies,
    UpdatePreferences,
)
from rinde.preferences.domain.errors import ReferenceCurrencyNotAllowedError
from rinde.preferences.domain.preferences import Preferences
from rinde.shared.domain.money import Currency
from rinde.shared.domain.rate_type import RateType
from tests.fakes import FakeClock, FakeTransaction, InMemoryPreferences

pytestmark = pytest.mark.anyio


def _deps() -> PreferencesDependencies:
    return PreferencesDependencies(
        preferences=InMemoryPreferences(), transaction=FakeTransaction(), clock=FakeClock()
    )


def test_bitcoin_cannot_be_the_reference_currency() -> None:
    with pytest.raises(ReferenceCurrencyNotAllowedError):
        Preferences(uuid4(), Currency.BTC, RateType.MEP)


async def test_without_choosing_anything_it_is_pesos_at_the_mep() -> None:
    owner = uuid4()

    preferences = await GetPreferences(_deps()).execute(owner)

    assert preferences == Preferences(owner, Currency.ARS, RateType.MEP)
    assert preferences.updated_at is None


async def test_a_change_is_kept_and_only_for_its_owner() -> None:
    deps = _deps()
    owner, someone_else = uuid4(), uuid4()

    await UpdatePreferences(deps).execute(owner, Currency.USD, RateType.BLUE)

    mine = await GetPreferences(deps).execute(owner)
    theirs = await GetPreferences(deps).execute(someone_else)
    assert (mine.reference_currency, mine.rate_type) == (Currency.USD, RateType.BLUE)
    assert mine.updated_at == FakeClock().now()
    assert (theirs.reference_currency, theirs.rate_type) == (Currency.ARS, RateType.MEP)
    assert deps.transaction.commits == 1  # type: ignore[attr-defined]


async def test_the_last_change_wins() -> None:
    deps = _deps()
    owner = uuid4()

    await UpdatePreferences(deps).execute(owner, Currency.USD, RateType.BLUE)
    deps.clock.advance(timedelta(minutes=1))  # type: ignore[attr-defined]
    await UpdatePreferences(deps).execute(owner, Currency.ARS, RateType.OFFICIAL)

    preferences = await GetPreferences(deps).execute(owner)
    assert (preferences.reference_currency, preferences.rate_type) == (
        Currency.ARS,
        RateType.OFFICIAL,
    )
