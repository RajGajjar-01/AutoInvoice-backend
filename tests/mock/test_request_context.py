import json

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.logging import setup_logging
from app.middleware.request_context import RequestContextMiddleware


def make_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)

    @test_app.get("/ping")
    async def ping() -> dict[str, str]:
        structlog.get_logger(__name__).info("ping_received")
        return {"ok": "true"}

    return test_app


def test_request_id_generated():
    response = TestClient(make_app()).get("/ping")
    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert response.json() == {"ok": "true"}


def test_incoming_request_id_is_honored():
    response = TestClient(make_app()).get("/ping", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"


def test_request_id_bound_to_log_output(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    setup_logging()
    TestClient(make_app()).get("/ping", headers={"X-Request-ID": "log-check-1"})
    lines = capsys.readouterr().out.strip().splitlines()
    events = [json.loads(line) for line in lines if line.startswith("{")]
    event = next(e for e in events if e["event"] == "ping_received")
    assert event["request_id"] == "log-check-1"
    assert event["http_path"] == "/ping"


def test_no_leak_between_requests(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    setup_logging()
    client = TestClient(make_app())
    client.get("/ping", headers={"X-Request-ID": "first"})
    client.get("/ping", headers={"X-Request-ID": "second"})
    events = [
        json.loads(line)
        for line in capsys.readouterr().out.strip().splitlines()
        if line.startswith("{")
    ]
    request_ids = [e["request_id"] for e in events if e["event"] == "ping_received"]
    assert request_ids == ["first", "second"]


@pytest.fixture(autouse=True)
def _reset_logging():
    yield
    import logging

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    structlog.reset_defaults()
