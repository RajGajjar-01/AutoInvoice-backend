go # Backend layered restructure: models / schemas / repositories / services

## Problem

`app/services/` exists but is empty. All business logic (ownership/permission
checks, validation, multi-step orchestration) currently lives directly in
route handlers (`app/api/routes/*.py`) or in a flat `app/crud.py` that mixes
thin DB access with a few business-rule functions (`validate_row_data`,
`duplicate_data_table`). `app/models.py` (747 lines) mixes SQLModel table
definitions with all Create/Update/Public DTO schemas for every domain.

This is consistent across all ~9 domains: customers, items, notifications,
company_settings, invoices, invoice_templates, tables (+rows+reminders),
users, admin/auth.

A sibling project, `backend-2`, already uses a layered structure
(`core/`, `models/`, `schemas/`, `repositories/`) with a `BaseRepository`
pattern, though it has no `services/` layer (it mostly proxies to Supabase
over raw SQL via asyncpg). This restructure adopts backend-2's folder
layout and repository pattern, adapted to this project's SQLAlchemy/SQLModel
stack (request path on `AsyncSession`, see "Async I/O" below), and adds
the `services/` layer backend-2 doesn't
need but this project does.

## Goals

- Populate `app/services/` with real business logic for every domain.
- Split `app/models.py` into `app/models/<domain>.py` (table classes only)
  and `app/schemas/<domain>.py` (DTOs only).
- Replace `app/crud.py` with `app/repositories/<domain>_repository.py`
  (pure data access, no business rules, no permission checks).
- Routes become thin: parse request → call service → return. No inline
  404/403 checks, no inline validation, no direct `session` manipulation
  in routes.
- Keep the current FastAPI response contract (`response_model` +
  `HTTPException`-shaped JSON bodies) — no frontend-facing changes.

## Non-goals

- No change to the API response envelope (no `{data, meta}` wrapper from
  backend-2 — explicitly rejected to avoid a frontend contract change).
- No change to authentication mechanism (JWT + cookies stay as-is).
- No async rewrite of Alembic, bootstrap scripts, or test fixtures — see
  "Async I/O" below for what does and doesn't go async, and why.
- No new database driver dependency — psycopg3 (already installed)
  handles both sync and async; asyncpg was considered and rejected.
- No full test-coverage push — only a minimal CRUD smoke test per
  currently-untested domain, not exhaustive coverage.

## Target directory structure

```
app/
  core/                  # unchanged: config.py, db.py, security.py
  exceptions.py          # expanded shared exception hierarchy
  models/                # SQLModel TABLE classes only — one file per domain
    __init__.py          # re-exports everything (keeps relationship string-refs resolvable)
    user.py  item.py  customer.py  table.py  invoice.py
    invoice_template.py  company_settings.py  notification.py
  schemas/               # Create/Update/Public/etc DTOs — one file per domain
    __init__.py
    common.py            # Message, Token, TokenPayload, NewPassword, PaginatedResponse
    user.py  item.py  customer.py  table.py  invoice.py
    invoice_template.py  company_settings.py  notification.py
  repositories/          # pure data access, no business rules, no permission checks
    __init__.py
    base.py              # generic BaseRepository[ModelType]
    user_repository.py  item_repository.py  customer_repository.py
    table_repository.py invoice_repository.py invoice_template_repository.py
    company_settings_repository.py  notification_repository.py
  services/              # business rules, ownership/permission checks, orchestration
    __init__.py
    user_service.py  item_service.py  customer_service.py  table_service.py
    invoice_service.py  invoice_template_service.py
    company_settings_service.py  notification_service.py
    email_service.py        # wraps current app/utils.py email functions
    excel_import_service.py # wraps parse_excel_file
  api/
    deps.py              # extended with per-domain repository/service providers
    routes/*.py          # thin: parse request → call service → return
```

`app/crud.py` and `app/models.py` are deleted once their contents are fully
redistributed.

## Layer responsibilities

**models/** — only `table=True` SQLModel classes and DB-only enums. No
validation logic, no business methods.

**schemas/** — `*Base/Create/Update/Public` DTOs. Pure I/O shapes, no DB
concerns.

**repositories/** — extend `BaseRepository[ModelType]`. Methods are
data-shape only: filtering, sorting, pagination, raw create/update/delete.
Take `owner_id` as a filter parameter but never decide what an absent
result *means* (no `HTTPException`, no business rules).

```python
class BaseRepository(Generic[ModelType]):
    def __init__(self, session: AsyncSession) -> None: self.session = session
    async def get(self, id: uuid.UUID) -> ModelType | None: ...
    async def add(self, obj: ModelType) -> ModelType: ...
    async def delete(self, obj: ModelType) -> None: ...

class TableRepository(BaseRepository[DataTable]):
    async def list_by_owner(self, owner_id, *, search, sort_by, sort_order, skip, limit) -> tuple[list[DataTable], int]: ...
    async def get_by_id_and_owner(self, table_id, owner_id) -> DataTable | None: ...
    async def add_row(self, table_id, data) -> TableRow: ...
    async def bulk_delete_rows(self, table_id, row_ids) -> int: ...
```

**services/** — own business rules and orchestration. Raise domain
exceptions (`NotFoundError`, `ForbiddenError`, `ConflictError`,
`ValidationError`) instead of `HTTPException`. This is where logic
currently embedded in routes/crud.py moves to: ownership checks,
`validate_row_data`, `duplicate_data_table`, invoice-template
activation-toggle logic, dashboard-stats aggregation, Excel-import
orchestration, password reset/change flows, etc.

```python
class TableService:
    def __init__(self, repo: TableRepository): self.repo = repo

    async def get_table(self, table_id, owner_id) -> DataTable:
        table = await self.repo.get_by_id_and_owner(table_id, owner_id)
        if not table:
            raise NotFoundError("Table not found")
        return table

    async def add_row(self, table_id, owner_id, row_in: TableRowCreate) -> TableRow:
        table = await self.get_table(table_id, owner_id)
        ok, missing = _validate_row_data(table.columns, row_in.data)
        if not ok:
            raise ValidationError(f"Missing mandatory fields: {', '.join(missing)}")
        return await self.repo.add_row(table_id, row_in.data)
```

**api/routes/*.py** — single service call per endpoint, no inline 404/403,
no inline validation:

```python
@router.post("/{table_id}/rows", response_model=TableRowPublic, status_code=201)
async def create_table_row(current_user: CurrentUser, table_id: uuid.UUID, row_create: TableRowCreate, service: TableServiceDep) -> Any:
    return await service.add_row(table_id, current_user.id, row_create)
```

**api/deps.py** — one provider pair per domain, same shape every time
(constructing a repository/service object isn't itself async — only the
methods that touch the DB are):

```python
def get_table_repository(session: SessionDep) -> TableRepository: return TableRepository(session)
def get_table_service(repo: TableRepository = Depends(get_table_repository)) -> TableService: return TableService(repo)
TableServiceDep = Annotated[TableService, Depends(get_table_service)]
```

## Error handling

Expand `app/exceptions.py` (currently only the `AuthError` family, wired to
a handler in `main.py` but never raised) with a shared hierarchy every
service uses:

```python
class NotFoundError(Exception):
    def __init__(self, message="Resource not found"): self.message = message

class ForbiddenError(Exception):
    def __init__(self, message="Not enough permissions"): self.message = message

class ConflictError(Exception):
    def __init__(self, message="Conflict"): self.message = message

class ValidationError(Exception):
    def __init__(self, message="Invalid request"): self.message = message
```

`app/main.py` gets one handler per exception type, alongside the existing
`AuthError` handler, mapping to the same `{"detail": ...}` shape
`HTTPException` already produces today (404 / 403 / 409 / 422
respectively). The existing `AuthError` family in `auth.py` keeps using
`HTTPException` for its simple login/signup error paths — only the newly
migrated domain logic raises the new hierarchy from inside services.

## Migration order

Scaffolding first, then domains ordered simple → complex so later domains
reuse patterns proven on earlier ones:

1. Scaffolding: `exceptions.py` additions, `main.py` handlers,
   `repositories/base.py`, `schemas/common.py`, empty `models/__init__.py`
   / `schemas/__init__.py`.
2. **User/Auth** (`users.py`, `auth.py`, `admin.py` — all share `User`) —
   foundational since `CurrentUser` touches it everywhere.
3. **Items** — simple single-model, has `test_items.py`.
4. **Customers** — simple single-model, no tests today.
5. **Notifications** — simple single-model, no tests today.
6. **Company Settings** — singleton-per-owner, no tests today.
7. **Tables** (+rows+reminders) — most complex, has `test_tables.py`.
8. **Invoice Templates** — medium complexity + Excel import, no tests today.
9. **Invoices** — depends on `Customer`, has dashboard-stats aggregation,
   no tests today.
10. Cleanup: delete `crud.py` and `models.py`, fix leftover imports, full
    `pytest` + `mypy --strict` + `ruff check` pass.

## Testing strategy

Domains with existing tests (`users`, `items`, `tables`, `login`,
`private`) must keep those tests green throughout — they are the
regression gate for unchanged HTTP behavior. Domains with no existing
tests (customers, notifications, company_settings, invoice_templates,
invoices, admin) get a minimal CRUD smoke test added as part of their
migration step — not exhaustive coverage, just enough to catch a broken
endpoint. After each domain step: `pytest`, `mypy --strict`,
`ruff check`.

## Async I/O

**Decision:** the request-serving path (routes → services → repositories)
runs on `AsyncSession`/`async def` throughout, on top of **psycopg3** —
not asyncpg. psycopg3 is already a dependency
(`psycopg[binary]>=3.2.0,<4.0.0`) and natively supports both sync and
async connections from the same package: SQLAlchemy picks sync vs async
based on `create_engine` vs `create_async_engine`, both against the same
`postgresql+psycopg://` URL scheme. This gets the real scalability benefit
(async I/O doesn't block a thread-pool slot per in-flight DB call, unlike
sync `Session` under FastAPI's default thread-pool execution) without a
second driver dependency. asyncpg was considered and rejected: it would
have meant two driver packages (one sync-only for Alembic/bootstrap/tests,
one async-only for the app) for a performance margin that doesn't matter
at this app's scale (CRUD/web-app query patterns, not high-frequency
bulk operations) — psycopg3 async gets ~95% of the benefit with zero
dependency duplication.

**Scope:** only the request path goes async. Alembic migrations,
`init_db`/bootstrap, and test fixtures (`tests/conftest.py`'s `db`
fixture, `tests/utils/*.py`) keep using the existing sync `engine`/
`Session` — these never run concurrently, so there's no scalability
upside to converting them, and Alembic's migration runner has no async
mode regardless. `TestClient` (httpx-based) calls into the now-async app
exactly as it does today; no test code needs `async def` or
`pytest-asyncio`, since `TestClient` drives the ASGI event loop
internally regardless of whether routes are sync or async.

**Mechanics:**
- `app/core/config.py` gains `ASYNC_SQLALCHEMY_DATABASE_URI`, the same
  URL as `SQLALCHEMY_DATABASE_URI` (reusing the same `POSTGRES_*`/
  `DATABASE_URL` settings, no new env vars).
- `app/core/db.py` gains `async_engine = create_async_engine(...)`
  alongside the existing sync `engine`.
- `app/api/deps.py`'s `get_db`/`SessionDep` move to
  `sqlmodel.ext.asyncio.session.AsyncSession`; `get_current_user` and
  every `get_X_repository`/`get_X_service` provider that touches the DB
  becomes `async def`.
- `BaseRepository` and every domain repository's methods become
  `async def`, using `await self.session.exec(...)`, `.commit()`,
  `.refresh()`, `.get()`, `.delete()` — the query-building code itself
  (the `select(...)` statements) is unchanged, since SQLModel's
  `AsyncSession` mirrors the sync `.exec()` API.
- Every service method becomes `async def`, `await`-ing repository
  calls. Validation/exception-raising logic is unchanged.
- Every route becomes `async def`, `await`-ing the service call.
  `response_model`, status codes, and path/query params are unchanged.
`ruff check`.
