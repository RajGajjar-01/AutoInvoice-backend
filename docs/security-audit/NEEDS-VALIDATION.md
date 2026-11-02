# Needs validation

These are prioritized leads. They have no severity and are not confirmed vulnerabilities. Each was fixed in code regardless; the owner checks below establish whether the pre-fix exposure was real in deployment.

## AI-004-no-auth-throttling: No application-level throttling or lockout on login, password recovery and signup

The unauthenticated login, password-recovery and signup endpoints have no rate limit or lockout in the repository. The sandboxed harness sent 30 wrong passwords then logged in successfully. Whether online guessing is practical depends on a fronting proxy, WAF or edge rate limit that the repository does not define. Fixed in-app regardless: per-IP and per-IP+account limits now return 429.

**Claimed root cause:** login_access_token calls crud.authenticate on every request without counting failures, and no throttling middleware exists; recover_password and register_user are likewise unthrottled.

### Trace
- `app/api/routes/login.py:26` (login_access_token): Unauthenticated POST /login/access-token takes username and password.
- `app/api/routes/login.py:35` (login_access_token): crud.authenticate is called with no attempt counter or lockout.
- `app/crud.py:52` (authenticate): Each guess is checked against the stored hash; failures are not recorded.

### Evidence
- `app/api/routes/login.py:38`: A failed login raises a plain 400 and records nothing.
- `app/main.py:51`: CORSMiddleware is the only middleware.
- `app/api/routes/login.py:148`: POST /password-recovery/{email} is unthrottled.
- `app/api/routes/users.py:145`: POST /users/signup is unthrottled.

### Blockers
- The repository does not show whether a reverse proxy, WAF, API gateway or edge rate limit throttles these endpoints in deployment.
- The local check shows no in-app throttling across 30 failures, not an account compromise, which depends on password strength and the attack rate the deployment allows.

### Resolution plan
- **local:** Already established: poc-baseline.json C5 shows no in-app throttling; poc-fixed.json C5 shows 429 after the fix.
- **deployment:** Check production routing (proxy, WAF or CDN rules) for rate limits on POST /api/v1/login/access-token, /api/v1/password-recovery/* and /api/v1/users/signup, or send a bounded burst of wrong passwords against a dedicated test account in staging and look for 429 or blocking. Note the in-app limiter is per process, so multi-worker or multi-replica deployments still need a shared limit.

## AI-008-insecure-default-environment: ENVIRONMENT defaulted to "local", turning on dev-only behaviour if a deployment did not set it

Settings.ENVIRONMENT defaulted to "local". That mounted the unauthenticated POST /api/v1/private/users/, set auth cookies without Secure, and only warned (instead of refusing to start) on SECRET_KEY/POSTGRES_PASSWORD/FIRST_SUPERUSER_PASSWORD = "changethis". The Dockerfile set neither ENVIRONMENT nor SECRET_KEY. Sandboxed checks C10 and C12 confirmed the code behaviour. Whether any deployment actually runs that way is not in the repository. Fixed regardless: the default is now production, the Dockerfile sets ENVIRONMENT=production, and short or default secrets fail startup outside local.

**Claimed root cause:** Security controls depend on an ENVIRONMENT setting that failed open, defaulting to the least-secure value.

### Trace
- `Dockerfile:46` (container CMD): The container starts with no ENVIRONMENT or SECRET_KEY in the image.
- `app/core/config.py:38` (Settings.ENVIRONMENT): Defaults to "local" when unset.
- `app/core/config.py:103` (Settings._check_default_secret): In local mode "changethis" secrets only warn, so a known SECRET_KEY would allow forging any user's JWT.

### Evidence
- `app/api/main.py:13`: The private router is mounted when local (C12: unauthenticated 200).
- `app/api/routes/login.py:56`: secure=settings.ENVIRONMENT != "local" on auth cookies.
- `app/core/config.py:33`: The built-in SECRET_KEY default is random, so the weak secret requires an operator to supply "changethis" (for example by copying .env.local).

### Blockers
- No production manifest is in the repository, so it is unknown whether any deployment ran with ENVIRONMENT unset or local.
- It is unknown whether any deployment supplied "changethis" secrets.

### Resolution plan
- **local:** C10/C12 in poc-baseline.json establish the code behaviour; poc-fixed.json C10 shows the weak secret is now rejected when ENVIRONMENT is unset.
- **deployment:** For each deployment, check the effective ENVIRONMENT (must be staging or production) and that SECRET_KEY, POSTGRES_PASSWORD and FIRST_SUPERUSER_PASSWORD are not "changethis". If any instance ran with a known SECRET_KEY, rotate it, since all issued tokens were forgeable.

## AI-009-csrf-cookie-auth: Cookie-authenticated mutations relied only on SameSite=Lax, with no CSRF token or Origin check

get_token accepted the ambient access_token cookie for every method with no CSRF token or Origin check. Explicit SameSite=Lax blocks ordinary cross-site CSRF in modern browsers, but a same-site, cross-origin attacker (a sibling subdomain or another port on the same host) can still send CORS-simple POSTs such as creating items or logging the user out. Whether such an origin exists depends on deployment topology. Fixed regardless: cookie-authenticated unsafe requests now require an Origin/Referer in CORS origins + CSRF_TRUSTED_ORIGINS, and the refresh cookie is SameSite=Strict.

**Claimed root cause:** Ambient-cookie authentication for unsafe methods with SameSite=Lax as the only CSRF defence.

### Trace
- `app/api/routes/items.py:60` (create_item): State-changing POST authenticated through CurrentUser.
- `app/api/deps.py:33` (get_token): The cookie is accepted for any method with no Origin check.
- `app/api/routes/login.py:57` (login_access_token): SameSite=Lax is the only CSRF control, which does not separate same-site sibling origins.

### Evidence
- `app/main.py:51`: CORS limits non-simple requests but does not stop simple POSTs being sent.
- `app/api/routes/login.py:134`: POST /login/logout is CORS-simple and cookie-authenticated.

### Blockers
- The production domain topology (other origins under the same registrable domain, and their trust level) is not in the repository.
- The supported browser set (legacy browsers without SameSite support) is not stated.

### Resolution plan
- **local:** In a headless browser logged in as a dummy user, send a credentialed fetch POST to /api/v1/items/ from a cross-site page and from a same-site sibling origin on loopback, and compare. After the fix both return 403 unless the origin is trusted (see test_cookie_auth_requires_trusted_origin).
- **deployment:** List the production API host and every origin under the same registrable domain, and whether any is less trusted; set CSRF_TRUSTED_ORIGINS to the exact frontend origins.
