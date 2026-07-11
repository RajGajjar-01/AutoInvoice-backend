# Deployment Guide — Environment Variables

This document lists every environment variable the backend reads (`app/core/config.py`), platform-independent. It doesn't matter whether you deploy to Railway, Render, Fly.io, a VPS, or anywhere else — these are the values you need to provide one way or another (`.env` file, platform's env var UI, secrets manager, etc.).

Two services must be reachable from wherever the backend runs: **PostgreSQL** and **Redis**. Neither is optional.

## Required — the app will not start without these

| Variable | Description |
|---|---|
| `SECRET_KEY` | Signs JWTs (access/refresh tokens, password-reset tokens, Google OAuth state tokens). Generate a long random string, e.g. `openssl rand -hex 32`. Must not be empty or the literal string `changethis` — both fail startup validation. |
| `ENVIRONMENT` | One of `local`, `staging`, `production`. Setting this to `production` turns on stricter validation (see below). |

## Database — provide ONE of these two options

**Option A — single connection string** (what Railway, Render, etc. usually inject automatically):

| Variable | Description |
|---|---|
| `DATABASE_URL` | Full Postgres connection string. Accepts `postgres://` or `postgresql://` prefixes — both are rewritten internally to the `postgresql+psycopg://` driver the app actually uses. |

**Option B — discrete fields** (used if `DATABASE_URL` is not set):

| Variable | Description |
|---|---|
| `POSTGRES_SERVER` | DB host |
| `POSTGRES_PORT` | DB port (default `5432`) |
| `POSTGRES_USER` | DB user |
| `POSTGRES_PASSWORD` | DB password — must not be the literal string `changethis` |
| `POSTGRES_DB` | DB name |

In `production`, startup validation requires either `DATABASE_URL` **or** all four of `POSTGRES_SERVER` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` to be set — otherwise the app refuses to boot.

Migrations run automatically on startup (`alembic upgrade head`, see `Dockerfile`/`docker-compose.yml`) — no separate manual migration step needed as long as the DB is reachable at boot.

## Redis — required

| Variable | Default | Description |
|---|---|---|
| `REDIS_SERVER` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |

Used for short-lived, rate-limited state: email-verification codes (signup) and Google OAuth state tokens. There's no `REDIS_URL`/password-auth variant currently — if your Redis provider requires auth or TLS, you'll need to extend `app/core/redis.py`.

## Frontend / CORS

| Variable | Description |
|---|---|
| `FRONTEND_HOST` | Full origin of the frontend, e.g. `https://app.example.com` (no trailing slash). Used to build links in emails (password reset, email verification) and as the redirect target after Google OAuth. **Required in `production`** — startup fails without it. Also automatically included in the allowed CORS origins. |
| `BACKEND_CORS_ORIGINS` | Comma-separated list of additional allowed CORS origins, e.g. `https://app.example.com,https://staging.example.com`. |

## Email (Brevo) — optional but required for any email-sending feature

Email-verification codes, password reset, and new-account emails are all sent through Brevo's transactional API. If unset, email sending is silently skipped where possible (e.g. signup won't email a verification code) but will hard-fail (500) if an email-only flow like "forgot password" is actually invoked.

| Variable | Description |
|---|---|
| `BREVO_API_KEY` | API key from brevo.com |
| `EMAILS_FROM_EMAIL` | Verified sender address in your Brevo account |
| `EMAILS_FROM_NAME` | Sender display name (defaults to `PROJECT_NAME` if unset) |

## Google OAuth — optional, required for "send invoices via Gmail"

If both are unset, the Google-connect feature is disabled (frontend `google_oauth_enabled` flag is `false`); nothing else breaks.

| Variable | Description |
|---|---|
| `GOOGLE_CLIENT_ID` | From Google Cloud Console OAuth client |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud Console OAuth client |
| `GOOGLE_REDIRECT_URI` | Must be `{your backend's public URL}/api/v1/google/callback`, and must also be registered as an authorized redirect URI in the Google Cloud Console for this OAuth client. Default assumes local dev (`http://localhost:8000/...`) — **always override this in any deployed environment.** |

## WhatsApp (OpenWA) — optional

| Variable | Default | Description |
|---|---|---|
| `OPENWA_BASE_URL` | `http://localhost:2785` | Base URL of your running OpenWA (open-wa) instance |
| `OPENWA_API_KEY` | *(empty)* | OpenWA API key |
| `OPENWA_SESSION_ID` | *(empty)* | OpenWA session identifier |

Only needed if you're running the separate OpenWA service and using the WhatsApp-invoice-sending feature.

## Initial superuser

| Variable | Default | Description |
|---|---|---|
| `FIRST_SUPERUSER` | `admin@example.com` | Email for the bootstrap admin account created on first startup (`app/initial_data.py`) |
| `FIRST_SUPERUSER_PASSWORD` | `changethis` | Password for that account — must not be left as `changethis`, or startup fails |

## Misc / rarely need changing

| Variable | Default | Description |
|---|---|---|
| `PROJECT_NAME` | `AutoInvoice` | Used in email subjects/branding |
| `API_V1_STR` | `/api/v1` | API route prefix |
| `PORT` | `8000` | Port the app listens on |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | JWT access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | JWT refresh token lifetime |
| `EMAIL_RESET_TOKEN_EXPIRE_HOURS` | `48` | Password-reset link lifetime |
| `EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES` | `10` | Signup verification code lifetime |
| `EMAIL_TEST_USER` | `test@example.com` | Recipient used by the `/utils/test-email` endpoint |
| `SENTRY_DSN` | *(unset — disabled)* | Set to enable Sentry error tracking |

## Quick checklist before going live

- [ ] `SECRET_KEY` set to a real random value (not empty, not `changethis`)
- [ ] `ENVIRONMENT=production`
- [ ] `DATABASE_URL` **or** all four discrete `POSTGRES_*` vars set
- [ ] `FRONTEND_HOST` set to your real frontend origin (required in production)
- [ ] `REDIS_SERVER` / `REDIS_PORT` point to a reachable Redis instance
- [ ] `POSTGRES_PASSWORD` and `FIRST_SUPERUSER_PASSWORD` are not `changethis`
- [ ] If using Google sign-in: `GOOGLE_REDIRECT_URI` updated to your real backend URL and registered in Google Cloud Console
- [ ] If emails need to send: `BREVO_API_KEY` + `EMAILS_FROM_EMAIL` set
