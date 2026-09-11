import json
import sys
from pathlib import Path

import pytest

from rinde import openapi


def test_exports_contract_with_health_endpoints(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"

    openapi.export(output)

    contract = json.loads(output.read_text(encoding="utf-8"))
    assert contract["info"]["title"] == "Rinde API"
    assert {"/api/health/live", "/api/health/ready"} <= contract["paths"].keys()


def test_main_writes_to_given_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "contrato.json"
    monkeypatch.setattr(sys, "argv", ["rinde.openapi", str(output)])

    openapi.main()

    assert output.exists()


def test_main_requires_output_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["rinde.openapi"])

    with pytest.raises(SystemExit, match="Uso"):
        openapi.main()
