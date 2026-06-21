# Backend layered restructure: models / schemas / repositories / services

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
+ sync `Session` stack, and adds the `services/` layer backend-2 doesn't
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
- No async rewrite — stays on sync SQLAlchemy `Session`.
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
    def __init__(self, session: Session) -> None: self.session = session
    def get(self, id: uuid.UUID) -> ModelType | None: ...
    def add(self, obj: ModelType) -> ModelType: ...
    def delete(self, obj: ModelType) -> None: ...

class TableRepository(BaseRepository[DataTable]):
    def list_by_owner(self, owner_id, *, search, sort_by, sort_order, skip, limit) -> tuple[list[DataTable], int]: ...
    def get_by_id_and_owner(self, table_id, owner_id) -> DataTable | None: ...
    def add_row(self, table_id, data) -> TableRow: ...
    def bulk_delete_rows(self, table_id, row_ids) -> int: ...
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

    def get_table(self, table_id, owner_id) -> DataTable:
        table = self.repo.get_by_id_and_owner(table_id, owner_id)
        if not table:
            raise NotFoundError("Table not found")
        return table

    def add_row(self, table_id, owner_id, row_in: TableRowCreate) -> TableRow:
        table = self.get_table(table_id, owner_id)
        ok, missing = _validate_row_data(table.columns, row_in.data)
        if not ok:
            raise ValidationError(f"Missing mandatory fields: {', '.join(missing)}")
        return self.repo.add_row(table_id, row_in.data)
```

**api/routes/*.py** — single service call per endpoint, no inline 404/403,
no inline validation:

```python
@router.post("/{table_id}/rows", response_model=TableRowPublic, status_code=201)
def create_table_row(current_user: CurrentUser, table_id: uuid.UUID, row_create: TableRowCreate, service: TableServiceDep) -> Any:
    return service.add_row(table_id, current_user.id, row_create)
```

**api/deps.py** — one provider pair per domain, same shape every time:

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
