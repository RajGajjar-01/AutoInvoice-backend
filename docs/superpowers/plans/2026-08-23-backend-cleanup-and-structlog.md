# Backend Cleanup & structlog Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all dead/duplicated/inconsistent code from the FastAPI backend and introduce structured logging end-to-end using structlog (JSON logs in staging/production, pretty console logs locally), with request-ID correlation.

**Architecture:** New `app/core/logging.py` configures structlog with a stdlib bridge (ProcessorFormatter) so uvicorn/gunicorn records flow through the same pipeline. A `RequestContextMiddleware` binds `request_id` via structlog contextvars. All modules switch from `logging.getLogger`/`print` to `structlog.get_logger`. Cleanup tasks precede logging so dead code never gets instrumented.

**Tech Stack:** Python 3.10+, FastAPI, SQLModel, uv, structlog, pytest, ruff, mypy.

**Spec:** Conversation requirements 2026-08-23 — "clean the backend code end to end; add logging with structlog". Findings source: exploration report 2026-08-23 (file:line references verified against working tree).

## Global Constraints

- Package manager is **uv** — always `uv add`, `uv remove`, `uv run`. Never pip.
- Python target **3.10** (ruff `target-version = "py310"`); keep syntax 3.10-compatible.
- Ruff select list stays as-is (`E,W,F,I,B,C4,UP,ARG001,T201`); do not weaken ignores.
- `alembic/` stays excluded from ruff/mypy; its stdlib `fileConfig` logging remains untouched.
- Public API responses/status codes must NOT change anywhere in this plan.
- Sentry integration, PII scrubber, rate limiting, security headers middleware stay intact.
- Every task ends with: `uv run mypy app` clean AND `uv run ruff check app scripts tests` clean AND `uv run pytest tests/mock -q` passing (unless the task itself is what makes them pass).
- One commit per task, conventional-commit style (`chore:`, `refactor:`, `feat:`, `fix:`).
- Integration tests (`tests/api/`) need Docker Postgres/Redis; run them when Docker is up, otherwise note deferral to CI in the task report.

---

### Task 1: Commit WIP and create work branch

**Files:** none created; existing uncommitted changes committed.

- [ ] **Step 1: Verify current state**

Run: `git status --short` (workdir `backend`)
Expected: ~10 modified files (`app/api/deps.py`, `app/exceptions.py`, `app/main.py`, `app/repositories/base.py`, `app/schemas/company_settings.py`, 5 services).

- [ ] **Step 2: Run existing gates before committing WIP**

Run: `uv run mypy app && uv run ruff check app`
Expected: clean (the WIP was previously CI-green). If dirty, fix minimally first — do not expand scope.

- [ ] **Step 3: Commit WIP on dev, then create branch**

```bash
git add -A && git commit -m "wip: service-layer adjustments before hygiene cleanup"
git checkout -b cleanup/hygiene-structlog
```

### Task 2: Delete dead code

**Files:**
- Modify: `app/main.py:222-227` (remove `/sentry-debug`)
- Modify: `app/api/routes/invoices.py:33` (unused logger)
- Modify: `app/services/google_oauth_service.py:9` (unused logger)
- Modify: `app/services/whatsapp_service.py:8` (unused logger)
- Modify: `app/services/email_service.py` (remove `generate_new_account_email`)
- Modify: `app/api/routes/utils.py` and possibly `app/api/main.py` (legacy health-check)

- [ ] **Step 1: Remove the temporary Sentry debug endpoint**

Delete `app/main.py` lines 222–227 entirely (the `# ⚠️  TEMPORARY` comment plus the `/sentry-debug` route).

- [ ] **Step 2: Remove unused loggers**

Delete these exact lines (each file's only remaining `logging` reference — also drop the `import logging` at top of each file if it becomes unused):
- `app/api/routes/invoices.py:33` — `logger = logging.getLogger(__name__)`
- `app/services/google_oauth_service.py:9` — same pattern
- `app/services/whatsapp_service.py:8` — same pattern

- [ ] **Step 3: Remove unused email generator**

In `app/services/email_service.py`, delete `generate_new_account_email()` (starts line 98). Then verify no template orphaned: `grep -rn "new_account" app templates` — if only the deleted function referenced a template file, delete that template file too (`templates/email-templates/build/new_account.html` if present).

- [ ] **Step 4: Remove legacy health-check route**

Read `app/api/routes/utils.py`. If `/health-check/` (lines 31–35) is the only endpoint in the file, delete the file and remove its import + `include_router` line from `app/api/main.py`. If other endpoints exist, delete only the health-check route.

Verify no caller breaks: `grep -rn "utils/health-check" app tests scripts` — update any test hitting it (expected: none, but check `tests/api/routes/test_main.py` style files for health-check assertions pointing at `/api/v1/utils/health-check/`; the canonical `/health` in `app/main.py:205` stays).

- [ ] **Step 5: Run gates**

Run: `uv run mypy app && uv run ruff check app && uv run pytest tests/mock -q`
Expected: all clean/passing.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: remove dead code (sentry-debug, unused loggers, legacy health-check, unused email generator)"
```

### Task 3: Dependency & tooling fixes

**Files:**
- Modify: `pyproject.toml` (deps + pytest config)
- Create: `.pre-commit-config.yaml`
- Modify: `.gitignore`, untrack `.env.local`
- Modify: lockfile via uv

- [ ] **Step 1: Fix dependencies**

```bash
uv remove httpx2          # dev dep, imported nowhere
uv add --dev pytest-timeout   # CI runs pytest with --timeout 60 today and fails
```

- [ ] **Step 2: Add pytest configuration**

Append to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Add pre-commit config for prek**

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: uv run ruff check app scripts tests
        language: system
        types: [python]
        pass_filenames: false
      - id: ruff-format
        name: ruff format --check
        entry: uv run ruff format --check app scripts tests
        language: system
        types: [python]
        pass_filenames: false
      - id: mypy
        name: mypy
        entry: uv run mypy app
        language: system
        types: [python]
        pass_filenames: false
```

Sanity-check prek accepts it: `uv run prek run --all-files || true` (hooks may take time; failure here means config typo — fix it).

- [ ] **Step 4: Untrack .env.local**

```bash
git rm --cached .env.local
grep -q "^\.env\.local$" .gitignore || printf "\n.env.local\n" >> .gitignore
```

- [ ] **Step 5: Run gates and commit**

Run: `uv sync && uv run mypy app && uv run ruff check app scripts tests && uv run pytest tests/mock -q`

```bash
git add -A && git commit -m "chore: fix deps (drop httpx2, add pytest-timeout), add pytest + prek config, untrack .env.local"
```

### Task 4: Deduplicate WhatsApp/document helpers in invoices routes

**Files:**
- Modify: `app/api/routes/invoices.py` (routes `send_invoice_email` L104+, `send_invoice_whatsapp` L155+, `send_invoice_reminder` L202+)

**Interfaces (produces):**
- `_document_label(invoice) -> str`
- `_pdf_filename(doc_label: str, invoice_number: str) -> str`
- `_resolve_whatsapp_service(default: WhatsAppService, company: <return type of CompanySettingsService.get_for_owner>) -> WhatsAppService`

- [ ] **Step 1: Add three private helpers** (place above `send_invoice_email`; annotate `company` with the concrete type used by `company_settings_service.get_for_owner`):

```python
def _document_label(invoice: Invoice) -> str:
    dt = (
        invoice.document_type.value
        if hasattr(invoice.document_type, "value")
        else invoice.document_type
    )
    return document_title_for(dt)


def _pdf_filename(doc_label: str, invoice_number: str) -> str:
    return f"{doc_label.lower().replace(' ', '_')}_{invoice_number}.pdf"


def _resolve_whatsapp_service(
    default: WhatsAppService, company: CompanySettingsPublic
) -> WhatsAppService:
    if company.whatsapp_enabled and company.openwa_api_key and company.openwa_session_id:
        return WhatsAppService(
            base_url=company.openwa_base_url,
            api_key=company.openwa_api_key,
            session_id=company.openwa_session_id,
        )
    return default
```

(Adjust `Invoice` / `CompanySettingsPublic` imports to whatever the file already imports; do not invent names.)

- [ ] **Step 2: Rewire the three routes** to call the helpers, deleting the three copies of the `dt = (...hasattr...)` block and the two copies of the conditional `WhatsAppService(...)` rebuild and the repeated filename f-strings. Route bodies otherwise unchanged; response payloads identical.

- [ ] **Step 3: Gates + commit**

Run: `uv run mypy app && uv run ruff check app && uv run pytest tests/mock -q`

```bash
git add -A && git commit -m "refactor: extract shared document-label/pdf-filename/whatsapp-service helpers in invoices routes"
```

### Task 5: Unify UTC datetime handling

**Files:**
- Modify: `app/core/security.py:155,157,165`
- Modify: `app/services/email_service.py:134`

- [ ] **Step 1:** Replace each `datetime.now(timezone.utc)` with `get_datetime_utc()` from `from app.core.time import get_datetime_utc`. Remove `timezone`/`datetime` imports from those files only if they become fully unused (keep if still referenced elsewhere in the file).

- [ ] **Step 2:** Gates + commit

Run: `uv run mypy app && uv run ruff check app && uv run pytest tests/mock -q`

```bash
git add -A && git commit -m "refactor: use core.time.get_datetime_utc everywhere instead of datetime.now(timezone.utc)"
```

### Task 6: Add structlog + core logging module (TDD)

**Files:**
- Modify: `pyproject.toml` via `uv add structlog`
- Modify: `app/core/config.py` (add `LOG_LEVEL`)
- Create: `app/core/logging.py`
- Test: `tests/mock/test_logging_config.py`

**Interfaces (produces):**
- `setup_logging() -> None` (idempotent; safe to call multiple times)
- `settings.LOG_LEVEL: str` (default `"INFO"`)

- [ ] **Step 1: Add dependency and setting**

```bash
uv add structlog
```

In `app/core/config.py`, inside `Settings` (next to `ENVIRONMENT`):

```python
LOG_LEVEL: str = "INFO"
```

- [ ] **Step 2: Write failing tests**

Create `tests/mock/test_logging_config.py`:

```python
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
    logging.getLogger("legacy.module").warning("disk nearly full: %s", "93%%")
    event = _last_event(capsys)
    assert event["event"] == "disk nearly full: 93%"
    assert event["level"] == "warning"
    assert event["logger"] == "legacy.module"


def test_log_level_respected(monkeypatch, capsys):
    monkeypatch.setattr(settings, "LOG_LEVEL", "WARNING")
    setup_logging()
    structlog.get_logger("test.level").info("quiet_info")
    assert capsys.readouterr().out == ""
```

- [ ] **Step 3: Verify tests fail**

Run: `uv run pytest tests/mock/test_logging_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.logging'`.

- [ ] **Step 4: Implement `setup_logging`**

Create `app/core/logging.py`:

```python
"""Centralized application logging built on structlog.

JSON output in staging/production, colored console output locally. Stdlib
records (uvicorn, gunicorn, third-party) are routed through the same
pipeline via ProcessorFormatter so every log line has one shape.
"""

import logging
import sys

import structlog

from app.core.config import settings


def setup_logging() -> None:
    """Configure structlog and the stdlib logging bridge. Idempotent."""
    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    renderer: structlog.typing.Processor
    if settings.ENVIRONMENT == "local":
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.LOG_LEVEL.upper())

    # Framework loggers must flow through the root handler, not their own.
    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "gunicorn.error",
        "gunicorn.access",
    ):
        framework_logger = logging.getLogger(name)
        framework_logger.handlers.clear()
        framework_logger.propagate = True

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
```

- [ ] **Step 5: Verify tests pass**

Run: `uv run pytest tests/mock/test_logging_config.py -v`
Expected: 4 passed. Then full mock tier: `uv run pytest tests/mock -q` — expected passing.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(logging): add structlog core module with stdlib bridge (JSON in prod, console in local)"
```

### Task 7: Request-ID middleware (TDD)

**Files:**
- Create: `app/middleware/request_context.py`
- Test: `tests/mock/test_request_context.py`

**Interfaces (produces):**
- `RequestContextMiddleware(BaseHTTPMiddleware)` — reads optional inbound `X-Request-ID`, generates uuid4 otherwise, binds `request_id`/`http_method`/`http_path` to structlog contextvars, echoes `X-Request-ID` on the response.

- [ ] **Step 1: Write failing tests** — create `tests/mock/test_request_context.py`:

```python
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
    event = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
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
```

- [ ] **Step 2: Verify tests fail**

Run: `uv run pytest tests/mock/test_request_context.py -v`
Expected: FAIL (`No module named 'app.middleware.request_context'`).

- [ ] **Step 3: Implement middleware** — create `app/middleware/request_context.py`:

```python
"""Binds a unique request ID to every log record emitted while handling a request."""

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        # Context vars are copied per asyncio task, so requests cannot bleed
        # into each other; binding here scopes these keys to this request.
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            http_method=request.method,
            http_path=request.url.path,
        )
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
```

- [ ] **Step 4: Verify tests pass**

Run: `uv run pytest tests/mock/test_request_context.py tests/mock/test_logging_config.py -v`
Expected: all pass. Full tier `uv run pytest tests/mock -q` passes.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(logging): add RequestContextMiddleware with X-Request-ID propagation"
```

### Task 8: Wire logging into app entrypoint + migrate all modules to structlog

**Files:**
- Modify: `app/main.py`
- Modify: `app/utils.py`, `app/backend_pre_start.py`, `app/tests_pre_start.py`, `app/initial_data.py`
- Modify: `app/api/routes/auth.py`, `app/api/routes/google_auth.py`
- Modify: `app/services/email_service.py`, `app/services/gmail_service.py`

- [ ] **Step 1: Entrypoint wiring** in `app/main.py`:

Add after the `app.add_middleware(SecurityHeadersMiddleware)` line (L182) — order matters: last-added middleware is outermost, so request IDs wrap everything:

```python
app.add_middleware(RequestContextMiddleware)
```

At top of module body, replace `logger = logging.getLogger(__name__)` (L29) with `logger = structlog.get_logger(__name__)` and add `from app.core.logging import setup_logging`. Call `setup_logging()` immediately after imports, BEFORE `if settings.SENTRY_DSN:` block (so init messages are captured). Normalize these callsites:

- L96–98 → `logger.info("Sentry initialized", environment=settings.ENVIRONMENT)`
- L134 → `logger.warning("Rate limit error", message=exc.message)`
- L201 → `logger.warning("Health check probe failed", check=name, error=str(exc))`

Remove `import logging` if now unused.

- [ ] **Step 2: Migrate remaining modules** — in each file: replace `logging.basicConfig(...)` deletion + `logger = logging.getLogger(__name__)` → `logger = structlog.get_logger(__name__)` (+ import), then normalize messages to kwargs:

| File | Change |
|---|---|
| `app/utils.py:7` | delete `logging.basicConfig(level=logging.INFO)` (library modules must not touch root config); L174 → `logger.error("Error parsing Excel file", error=str(e))` |
| `app/backend_pre_start.py:7` | delete basicConfig; L17/L19 → `logger.info("...", ...)` kwargs form |
| `app/tests_pre_start.py:7` | same as above |
| `app/initial_data.py:7` | same as above |
| `app/api/routes/auth.py:33` | swap factory; L98–100, L238–240, L269–271 → `logger.warning("[DEV] Verification code sent", email=user.email)` — NOTE: keep the actual `code` value OUT of structured logs even in dev mode; print-to-console UX is preserved by keeping the message text informative |
| `app/api/routes/google_auth.py:18` | swap factory; L85 `logger.exception("Google OAuth token exchange failed")` unchanged (works natively) |
| `app/services/email_service.py:16` | swap factory; L68 → `logger.info("Brevo email accepted", status=response.status_code)` — stop dumping full response JSON |
| `app/services/gmail_service.py:10` | swap factory; L49 → `logger.info("Gmail send completed", message_id=result.get("id"))` |

- [ ] **Step 3: Verify no stragglers**

Run: `grep -rn "logging.getLogger\|basicConfig" app/ | grep -v alembic`
Expected: no matches outside `app/alembic/`.
Run: `grep -rn "^import logging" app/` — only files that genuinely still need stdlib (expected: none in app/, aside from alembic env excluded).

- [ ] **Step 4: Gates**

Run: `uv run mypy app && uv run ruff check app scripts tests && uv run pytest tests/mock -q`
Expected: clean. Smoke-boot check if Docker DB available: `timeout 15 uv run uvicorn app.main:app --port 8000` — startup logs render through structlog (JSON unless ENVIRONMENT=local); Ctrl-C/timeout kill is fine. If DB unavailable, note deferral in report.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(logging): wire setup_logging + RequestContextMiddleware into app; migrate all modules to structlog"
```

### Task 9: Final verification & docs

**Files:**
- Modify: `backend/README.md` (logging section), `scripts/lint.sh` (extend scope)

- [ ] **Step 1: Extend lint script coverage** — in `scripts/lint.sh`, change the ruff invocations from `app`-only to `app scripts tests` for both `ruff check` and `ruff format --check`.

- [ ] **Step 2: Document logging** — add a short "Logging" section to `README.md`: structlog-based; JSON when `ENVIRONMENT != local`, colored console otherwise; `LOG_LEVEL` env var; every response carries `X-Request-ID` which appears as `request_id` in all log lines.

- [ ] **Step 3: Full gate suite**

```bash
uv run scripts/lint.sh
uv run pytest tests/mock -q
# If Docker available: docker compose up -d db redis && sleep 5 && uv run pytest tests/api -v --timeout 60
```

Expected: lint clean, mock tier passing; integration tier either green here or explicitly deferred to CI in the report.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "docs+ci: extend lint.sh scope, document structlog logging conventions"
```
