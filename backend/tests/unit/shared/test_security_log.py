"""El formato del registro de seguridad: lo que queda escrito y lo que nunca entra (ADR-0035)."""

import json
import logging
from collections.abc import Callable
from datetime import datetime
from io import StringIO
from typing import Any

from rinde.shared.infrastructure.security_log import (
    LOGGER_NAME,
    MAX_URI_LENGTH,
    Level,
    SecurityEventFormatter,
    configure_security_log,
    record_security_event,
)

Events = Callable[[], list[dict[str, Any]]]


def test_an_event_is_one_json_line_with_the_owasp_fields(security_events: Events) -> None:
    record_security_event(
        "authn_login_fail",
        ["5f0c3c1e-1111-4222-8333-944444444444"],
        level=Level.WARN,
        description="Inicio de sesión fallido",
        source_ip="203.0.113.7",
    )

    [line] = security_events()
    assert line == {
        "datetime": line["datetime"],
        "appid": "rinde.api",
        "event": "authn_login_fail:5f0c3c1e-1111-4222-8333-944444444444",
        "level": "WARN",
        "description": "Inicio de sesión fallido",
        "source_ip": "203.0.113.7",
    }
    assert datetime.fromisoformat(line["datetime"]).utcoffset() is not None


def test_params_follow_the_vocabulary_separated_by_commas(security_events: Events) -> None:
    record_security_event(
        "excess_rate_limit_exceeded", ["login_failure", "30"], level=Level.WARN, description="x"
    )
    record_security_event("csrf_rejected", [], level=Level.WARN, description="x")

    assert [line["event"] for line in security_events()] == [
        "excess_rate_limit_exceeded:login_failure,30",
        "csrf_rejected",
    ]


def test_a_value_from_outside_cannot_forge_another_line() -> None:
    """CWE-117: una ruta con salto de línea no parte el registro en dos."""
    stream = StringIO()
    logger = logging.getLogger(LOGGER_NAME)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SecurityEventFormatter())
    logger.addHandler(handler)
    previous = logger.level
    logger.setLevel(logging.INFO)
    try:
        forged = '/api\n{"event":"authn_login_success","level":"INFO"}\r' + chr(0x2028)
        record_security_event(
            "origin_rejected", [], level=Level.WARN, description="x", request_uri=forged
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["request_uri"] == forged


def test_a_huge_path_is_cut(security_events: Events) -> None:
    record_security_event(
        "origin_rejected", [], level=Level.WARN, description="x", request_uri="/" + "a" * 5000
    )

    [line] = security_events()
    assert len(line["request_uri"]) == MAX_URI_LENGTH


def test_only_the_closed_list_of_fields_is_written(security_events: Events) -> None:
    """Quien use el logger a mano no puede colar campos: se descartan."""
    logging.getLogger(LOGGER_NAME).warning(
        "contraseña: %s", "mi gato come fideos", extra={"password": "secreta"}
    )

    [line] = security_events()
    assert set(line) == {"datetime", "appid", "event", "level"}
    assert "secreta" not in json.dumps(line)
    assert "fideos" not in json.dumps(line)


def test_levels_map_to_python_levels(security_events: Events) -> None:
    for level in Level:
        record_security_event("x", [], level=level, description="x")

    assert [line["level"] for line in security_events()] == ["INFO", "WARN", "CRITICAL"]


def test_configuring_twice_does_not_duplicate_lines() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    before = list(logger.handlers)
    try:
        configure_security_log(StringIO())
        configure_security_log(StringIO())
        added = [handler for handler in logger.handlers if handler not in before]
        assert len(added) <= 1
        assert logger.propagate is False
    finally:
        for handler in logger.handlers:
            if handler not in before:
                logger.removeHandler(handler)
