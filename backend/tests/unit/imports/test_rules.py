"""Reglas de categoría (ADR-0024): texto contenido, plegado, y gana la más específica."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from rinde.imports.domain.errors import RulePatternInvalidError
from rinde.imports.domain.rules import CategoryRule, best_rule, pattern_from

OWNER = uuid4()
NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)


def rule(pattern: str, *, is_expense: bool = True) -> CategoryRule:
    return CategoryRule(uuid4(), OWNER, pattern_from(pattern), uuid4(), is_expense, NOW)


class TestTexto:
    def test_se_guarda_plegado_y_sin_espacios_de_mas(self) -> None:
        assert pattern_from("  Panadería   La  Esquina ") == "panaderia la esquina"

    @pytest.mark.parametrize("raw", ["", "  ", "ab", "x" * 61])
    def test_muy_corto_o_muy_largo(self, raw: str) -> None:
        with pytest.raises(RulePatternInvalidError):
            pattern_from(raw)


def test_a_rule_applies_when_the_description_contains_it() -> None:
    coto = rule("Coto")

    assert coto.applies_to("COMPRA COTO SUC 123", is_expense=True)
    assert coto.applies_to("compra  cotó", is_expense=True)
    assert not coto.applies_to("CARREFOUR", is_expense=True)
    assert not coto.applies_to(None, is_expense=True)


def test_a_rule_only_applies_to_its_kind() -> None:
    assert not rule("haberes").applies_to("HABERES OCTUBRE", is_expense=False)
    assert rule("haberes", is_expense=False).applies_to("HABERES OCTUBRE", is_expense=False)


def test_the_most_specific_wins() -> None:
    coto, digital = rule("coto"), rule("coto digital")

    assert best_rule([coto, digital], "COTO DIGITAL ENVIO", is_expense=True) is digital
    assert best_rule([coto, digital], "COTO SUC 12", is_expense=True) is coto
    assert best_rule([coto, digital], "DIA", is_expense=True) is None


def test_a_tie_in_length_is_broken_alphabetically() -> None:
    first, second = rule("aaa"), rule("bbb")

    assert best_rule([second, first], "BBB AAA", is_expense=True) is first
