import json
import logging

import pytest
import structlog

from app.core.config import settings
from app.core.logging import setup_logging


@pytest.fixture(autouse=True)
def _reset_logging():
    yield
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    structlog.reset_defaults()


def _last_event(capsys) -> dict:
    out = capsys.readouterr().out.strip().splitlines()[-1]
    return json.loads(out)


def test_json_output_when_not_local(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    setup_logging()
    structlog.get_logger("test.json").info("order_created", invoice_id=42)
    event = _last_event(capsys)
    assert event["event"] == "order_created"
    assert event["invoice_id"] == 42
    assert event["level"] == "info"
    assert "timestamp" in event


def test_console_output_in_local(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "local")
    setup_logging()
    structlog.get_logger("test.local").info("hello_local")
    out = capsys.readouterr().out
    assert "hello_local" in out
    with pytest.raises(json.JSONDecodeError):
        json.loads(out.strip().splitlines()[-1])


def test_stdlib_logs_flow_through_pipeline(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    setup_logging()
    logging.getLogger("legacy.module").warning("disk nearly full: %s", "93%")
    event = _last_event(capsys)
    assert event["event"] == "disk nearly full: 93%"
    assert event["level"] == "warning"
    assert event["logger"] == "legacy.module"


def test_log_level_respected(monkeypatch, capsys):
    monkeypatch.setattr(settings, "LOG_LEVEL", "WARNING")
    setup_logging()
    structlog.get_logger("test.level").info("quiet_info")
    assert capsys.readouterr().out == ""
