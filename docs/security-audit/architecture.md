# Architecture (run-1)

1. **Product:** AutoInvoice backend, a FastAPI REST API (based on the full-stack-fastapi template).
   - **Principals:** anonymous visitors (signup, login, password recovery), authenticated users (own profile and own items), and superusers (all users and items, test email, recovery HTML).
   - **Protected resources:** user accounts and credentials, and items per owner.
2. **Comparable software:** the upstream full-stack-fastapi-template. It shares the reset-token and stateless-JWT pattern; this fork added cookie auth and refresh tokens without type separation.
3. **Stack:**
   - Python 3.10+, FastAPI 0.129, SQLModel/SQLAlchemy 2.0, PostgreSQL 16, PyJWT HS256, pwdlib (argon2/bcrypt), Jinja2 email templates, Sentry.
   - Deploy: Dockerfile (`fastapi run --workers 4`); docker-compose for the DB only; Windows `start.bat` for dev.
   - Offline tests: pytest against a local Postgres.
4. **Entry surfaces:** `/api/v1/login/*`, `/password-recovery/{email}`, `/reset-password/`, `/users/*`, `/items/*`, `/utils/*`, and `/private/users/` (local only). Key paths:
   - token issue (`login.py`) → verify (`deps.get_current_user`);
   - recovery → reset (`utils.py`, `login.py`);
   - settings (`core/config.py`) gating private routes, cookie flags and secret checks.
5. **Trust boundaries and their strongest controls:**
   - anonymous → user: JWT signature and expiry;
   - user → other users' items: owner check in `items.py`;
   - user → superuser: `get_current_active_superuser`;
   - browser cross-site: `SameSite=Lax` cookies plus the CORS allow-list.
6. **Starting paths:** `app/api/deps.py`, `app/api/routes/login.py`, `app/api/routes/users.py`, `app/core/security.py`, `app/core/config.py`, `app/utils.py`.
7. **Prior coverage:** none (first run).
8. **Companions:**
   - Selected: `WEB-PROTOCOL-AND-AUTH.md` (browser-session cookies, CSRF), `CLOUD-AND-DEPLOYMENT.md` (env-gated controls, Dockerfile), `DATA-ISOLATION-AND-LIFECYCLE.md` (session revocation lifecycle).
   - Excluded: federated identity and API-key/mTLS (absent from source), AI, desktop, mobile, memory safety and protocols (not present).
