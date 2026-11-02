# AutoInvoice Backend

A FastAPI + PostgreSQL backend. PostgreSQL runs in Docker; FastAPI runs locally.

---

## ⚡ Quick Start (Windows)

**Prerequisites:** [Docker Desktop](https://www.docker.com/) must be installed and running.

### 1. Set up the virtual environment (first time only)

Install [uv](https://docs.astral.sh/uv/) if you haven't already:
```
pip install uv
```

Then from the `AutoInvoice-backend/` directory:
```
uv sync
```

### 2. Start the backend

Simply double-click **`start.bat`** or run it in a terminal:
```
start.bat
```

This will:
1. Start the PostgreSQL database in Docker
2. Wait until the database is healthy
3. Launch FastAPI with hot-reload enabled

**Database tables are created automatically** on first run — no manual migration step needed.

### 3. Stop the backend

Press `CTRL+C` in the terminal to stop FastAPI, then run:
```
stop.bat
```

Your database data is preserved between restarts. Only run `docker compose down -v` if you want to **wipe all data and start fresh**.

---

## URLs

| Service | URL |
|---------|-----|
| FastAPI API | http://localhost:8000 |
| Interactive API Docs (Swagger) | http://localhost:8000/docs |
| Alternative Docs (ReDoc) | http://localhost:8000/redoc |

---

## Troubleshooting

### "relation does not exist" / Table not found
This means the database tables weren't created. **This is now fixed automatically** — the app creates all tables on startup. If you're still seeing it:
1. Make sure Docker is running: `docker compose up -d`
2. Restart FastAPI — it will auto-create tables on the next startup

### "Connection refused" / Network error
The database isn't running. Run `docker compose up -d` first, wait ~10 seconds, then start FastAPI.

### Docker health check failing
Try:
```
docker compose down
docker compose up -d
docker compose logs db
```

### Starting completely fresh (wipe all data)
```
docker compose down -v
start.bat
```

---

## Manual Workflow (Advanced)

If you prefer to run steps manually instead of using `start.bat`:

```bash
# 1. Start the database
docker compose up -d

# 2. Activate the virtual environment
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # Mac/Linux

# 3. (Optional) Run Alembic migrations explicitly
alembic upgrade head

# 4. Start FastAPI
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

## Database Migrations (Alembic)

When you change models in `app/models.py`, create and apply a migration:

```bash
# Generate a new migration file automatically
alembic revision --autogenerate -m "describe your change here"

# Apply migrations to the database
alembic upgrade head
```

> **Note:** Even without running migrations, the app uses `SQLModel.metadata.create_all()` as a fallback to ensure tables always exist.

---

## Project Structure

```
AutoInvoice-backend/
├── app/
│   ├── api/           # API route handlers
│   ├── alembic/       # Database migration files
│   ├── core/
│   │   ├── config.py  # Settings (reads from .env)
│   │   ├── db.py      # Database engine & init
│   │   └── security.py
│   ├── crud.py        # Database operations
│   ├── models.py      # SQLModel data models
│   └── main.py        # FastAPI app entrypoint
├── scripts/
│   └── prestart.sh    # Startup script (used in Docker containers)
├── .env               # Environment variables (not committed to git)
├── docker-compose.yml # PostgreSQL in Docker
├── start.bat          # 🚀 One-click Windows startup
└── stop.bat           # 🛑 Windows shutdown
```

---

## Security configuration

See [`docs/security-audit/REPORT.md`](docs/security-audit/REPORT.md) for the latest security audit.

- **`ENVIRONMENT` defaults to `production`.** For local development set `ENVIRONMENT=local` in `.env` (copy `.env.local` to `.env`). Outside `local`, startup fails if `SECRET_KEY`, `POSTGRES_PASSWORD` or `FIRST_SUPERUSER_PASSWORD` is `changethis`, if `SECRET_KEY` is shorter than 32 characters, or if CORS origins contain `*`. Generate a key with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- **Apply migrations** after pulling: `alembic upgrade head` adds `user.token_version`, which is used to revoke sessions. The app also adds the column automatically on startup if it is missing.
- **Sessions:** logout, password change/reset, and admin changes to a user's email, password, active or superuser flags revoke all of that user's tokens.
- **CSRF:** cookie-authenticated `POST/PUT/PATCH/DELETE` requests must send an `Origin` (or `Referer`) that is in `BACKEND_CORS_ORIGINS`, `FRONTEND_HOST` or `CSRF_TRUSTED_ORIGINS`. Requests using `Authorization: Bearer` are unaffected.
- **Rate limiting** (`RATE_LIMIT_*` settings) is in-process. With several workers or replicas, also enforce a limit at your proxy or edge.
- **API changes:** `POST /users/signup` now returns `{"message": ...}` for both new and existing emails (no account enumeration). `PATCH /users/me` requires `current_password` when changing `email`. List endpoints accept `limit` from 1 to 100.
