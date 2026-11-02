# Security audit: AutoInvoice-backend

**Run:** `run-1` · **Profile:** `quick`, a partial pass rather than an exhaustive review · **Source:** commit `a16ba19` (clean worktree) · **Date:** 2026-11-02
**Method:** the [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) workflow (recon, a hunting wave, a coverage critic, independent verification of every candidate, schema-validated `findings.json` and `coverage-ledger.json`), cross-checked against the OWASP Top 10.
**Execution:** source review plus bounded local checks only. The local checks ran inside a fresh network namespace with loopback only (external DNS confirmed unreachable), an empty allow-listed environment, `prlimit` CPU, memory, process and file-size limits, a 300 s timeout, a disposable source copy, a throwaway local PostgreSQL and dummy principals. No deployed endpoint was contacted.
**Prior runs:** none. No earlier ledger existed, so this run is not a complete-coverage claim.
**Budget:** none set. Seven agent roles were used: parent hunter, three candidate verifiers, a coverage critic, a verifier for the critic's leads, and a post-fix check.

**Deviation from the skill:** the parent agent did reconnaissance and hunting itself rather than through separate hunter agents, because the codebase is small (about 1,000 lines of application code). Every candidate was still verified by a fresh agent that had not produced it. The skill's audit phase only *describes* fixes; at the user's request, the fixes were also implemented, on branch `claude/hopeful-darwin-acqh4b`.

## Security posture

The core authorization model (owner and superuser checks, no mass assignment of privilege fields, ORM-only SQL, argon2 hashing with a timing-safe login) is sound. The weaknesses were in **session and token lifecycle**:
- the JWT types were interchangeable;
- tokens were never revoked;
- reset links could be replayed;
- an email could be changed without re-authentication.

Together, a briefly stolen access token could become persistent account control. A second cluster was **fail-open defaults**: `ENVIRONMENT` defaulted to `local`, there was no throttling, and there was no CSRF origin check. All of these are fixed in the branch.

## Confirmed findings

| Severity | Fingerprint | Title | Boundary | Observed result (before fix) |
|---|---|---|---|---|
| medium | AI-001-jwt-token-type-confusion | Access and refresh JWTs are interchangeable | Session expiry | Access token in `refresh_token` cookie minted new tokens indefinitely (200) |
| medium | AI-002-no-token-revocation-on-credential-change | Tokens survive password change, reset and logout | Session revocation | Old access and refresh tokens returned 200 after password change |
| medium | AI-003-reset-token-replay | Reset tokens reusable for 48 h | Password reset | Same token reset the password twice (200, 200) |
| medium | AI-010-email-change-without-reauth | Email change without current password enables takeover through recovery | Account recovery channel | Source trace: token → change email → recovery → new password |
| low | AI-006-signup-account-enumeration | Signup reveals registered emails | Anti-enumeration | 400 "already exists" for registered addresses |

### AI-001: JWT token type confusion (medium)
- **Location:** `app/api/routes/login.py:84-131`, `app/api/deps.py:47-58`, `app/core/security.py:22-38`.
- **Principal:** someone holding a stolen 15-minute access token.
- **Reproduction:** `POST /api/v1/login/refresh` with `Cookie: refresh_token=<access token>` returns a fresh token, and this repeats indefinitely. A refresh token is also accepted as a Bearer token, and a reset token used as Bearer caused a 500.
- **Fix:** every token now carries a `type` claim (`access`, `refresh` or `password_reset`) plus `iat`, `nbf` and `jti`. One `decode_token(token, expected_type)` helper requires those claims and enforces the type. Refresh tokens rotate on use, and the refresh cookie is now `SameSite=Strict`.

### AI-002: No token revocation (medium)
- **Location:** `app/api/routes/users.py:102-120`, `login.py:134-192`.
- **Principal:** someone holding stolen tokens after the victim rotates their password.
- **Fix:** a new `user.token_version` column (Alembic `b7c1d2e3f4a5`, plus a safety net in `init_db`) is embedded as the `ver` claim and compared on every request. It is incremented on:
  - password change and reset;
  - logout, which now revokes all of the user's sessions;
  - admin changes to `email`, `password`, `is_active` or `is_superuser`.

### AI-003: Reset-token replay (medium)
- **Location:** `app/utils.py:103-122`, `login.py:172-192`.
- **Fix:** each reset token is bound to an HMAC fingerprint of the current password hash, so it is single-use and invalidated by any password change. Expiry is shortened from 48 h to 1 h, `sub` is the user id, the reset revokes existing sessions, and the endpoint is rate-limited.

### AI-010: Email change without re-authentication (medium)
- **Location:** `app/api/routes/users.py:80-99`.
- **Attack chain:** a token thief PATCHes the email to their own address, triggers password recovery, and resets the password. The victim is permanently locked out.
- **Fix:** `current_password` is required whenever the email changes, emails are normalized to lower case, and the change is logged.

### AI-006: Signup enumeration (low)
- **Location:** `app/api/routes/users.py:145-158`.
- **Fix:** signup returns an identical generic `Message` whether or not the email exists, notifies the existing owner by email, and is rate-limited per IP.
- ⚠️ **API contract change:** `/users/signup` now returns `{"message": ...}` instead of `UserPublic`. The frontend must not rely on the returned user object.

## NEEDS VALIDATION (no severity assigned)

| Fingerprint | Title | Blocker | Local next step | Owner check |
|---|---|---|---|---|
| AI-004-no-auth-throttling | No in-app throttling on login, recovery and signup | Unknown whether a proxy, WAF or edge rate limit exists | Done: 30 failures then success (before fix), 429 after | Inspect edge rate-limit rules for `/login/access-token`, `/password-recovery/*`, `/users/signup` |
| AI-008-insecure-default-environment | `ENVIRONMENT` defaulted to `local` | Unknown whether any deployment ran with it unset, or with `changethis` secrets | Done: C10, C12 | Verify every deployment's `ENVIRONMENT` and secrets; **rotate `SECRET_KEY` if it was ever `changethis`** |
| AI-009-csrf-cookie-auth | Cookie auth relied on `SameSite=Lax` only | Production same-site topology unknown | Headless-browser same-site vs cross-site fetch | List sibling origins under the API's registrable domain; set `CSRF_TRUSTED_ORIGINS` |

All three are nevertheless **fixed in code**:
- **AI-004:** an in-process sliding-window limiter (`app/core/rate_limit.py`) applies per-IP limits and per-IP-and-account failure lockout, and returns 429.
- **AI-008:** `ENVIRONMENT` defaults to `production`, the Dockerfile sets `ENVIRONMENT=production`, and outside `local` a `SECRET_KEY` shorter than 32 characters or wildcard CORS fails startup.
- **AI-009:** cookie-authenticated unsafe methods must carry an `Origin` or `Referer` in the CORS origins or `CSRF_TRUSTED_ORIGINS`.

## Rejected candidates (not findings)
- **AI-005, cookie precedence over Bearer:** no boundary crossing. Fixed anyway as a correctness bug: the Authorization header now wins. This was also the cause of 17 order-dependent test failures on `main`.
- **AI-007, unbounded `limit`:** self-impact only. Capped anyway: `skip>=0`, `1<=limit<=100`.
- **AI-011, signup without email verification:** no source-visible boundary.

## Hardening applied (not findings)
- **Response headers:**
  - `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy` and COOP;
  - `Content-Security-Policy: default-src 'none'` for the API;
  - HSTS outside `local`;
  - `Cache-Control: no-store` on API responses.
- **Docs:** `/docs`, `/redoc` and `openapi.json` are disabled in `production`.
- **Email templates:** Jinja templates render with autoescape, and the plaintext password is no longer emailed for admin-created accounts.
- **Header bug:** the invalid response header `subject:` became `X-Email-Subject`.
- **Lookups:** email lookups are case-insensitive.
- **Logging:** security events are logged (login success and failure, password change and reset, email change, logout) without secrets.
- **Containers and local dev:**
  - the Dockerfile runs as a non-root `appuser`;
  - docker-compose binds Postgres to `127.0.0.1`;
  - `start.bat` binds uvicorn to `127.0.0.1`;
  - `.dockerignore` excludes `.env*`, `.git` and `tests`.

## Remaining recommendations
1. The rate limiter is per process (the Dockerfile runs 4 workers). For a global limit, add an edge or proxy limiter, or a Redis-backed one.
2. Add email verification for signup and for email changes (confirm at the new address, notify the old one).
3. `emails==0.6` (with premailer, cssutils and chardet) is effectively unmaintained; consider replacing it with `smtplib` or a maintained library.
4. If `SECRET_KEY` was ever a known value in any environment, rotate it.

## Coverage summary
- **Ledger:** 7 units, all assigned; 5 have candidates, 2 are covered clean (injection, dependencies); 0 blocked or deferred.
- **Final critic:** ran, and found 2 new leads (AI-010 confirmed, AI-011 rejected) plus hardening items.
- **Areas the critic found clean:** IDOR and ownership, mass assignment, SQL, template and header injection, SSRF, secrets in the repo, and dependency CVEs (no confident match in `uv.lock`).
- **Not covered:** this is a `quick` run. Production deployment configuration is outside the repository, and the frontend was not in scope.

## Verification of fixes
- **Tests:** 80 pass (the baseline had 17 failures). 18 new security regression tests are in `tests/api/routes/test_security.py`, with more in `test_users.py`.
- **Static checks:** `ruff check` and `mypy app` (strict) are clean.
- **Migration:** `alembic upgrade head`, `downgrade -1` and `upgrade head` all succeed.
- **Harness rerun on the fixed source** (`agents/parent-fixcheck/artifacts/poc-fixed.json`):
  - C1, C2, C3 and C9 now return 403;
  - C4 returns 200 then 400;
  - C5 returns 429;
  - C7 gives an identical response for existing and new emails;
  - C8 returns 422;
  - C10 is rejected.
