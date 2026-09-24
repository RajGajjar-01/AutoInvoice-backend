# Google Sign-In + Claims-Based JWT — Design

Date: 2026-09-25
Repos: backend (most changes), frontend (login/signup/settings UI)

## Goals

1. Users can sign up / log in with Google from the login and signup pages.
2. ChatGPT-style account rules: a Google-created account has no password and can
   only log in with Google until the user sets a password in Settings; after that
   both methods work.
3. Access JWT carries authorization claims so most requests need no DB lookup.

## Non-goals

- Other OAuth providers (GitHub, Microsoft, Apple). Google only.
- Server-side refresh-token tracking / rotation / revocation (explicitly deferred).
- Google app verification (owner accepts the "unverified app" warning for now).

## Decisions (agreed in brainstorming)

| Topic | Decision |
|---|---|
| JWT | Claims in access token; no per-request DB lookup for most routes |
| Existing email on Google login | Auto-link only if Google `email_verified` AND local `is_verified`; else refuse |
| Scopes | Sign-in requests `openid email profile gmail.send` in one consent |
| Data model | Columns on `user`, no identities table |

## Data model

One Alembic migration:

- `user.google_sub: str | None` — unique, indexed. Google's stable account id; the
  only key used to match Google logins (never email).
- `user.hashed_password` becomes nullable. `NULL` == Google-only account.
- Existing `google_email`, `google_access_token`, `google_refresh_token`,
  `google_token_expires_at` are reused unchanged (tokens stay encrypted).

`UserPublic` gains `has_password: bool` (computed) so the UI can choose
"Set password" vs "Change password". `google_sub` is not exposed.

## JWT

Access token claims: `sub`, `type="access"`, `email`, `is_superuser`,
`is_verified`, `iat`, `exp`, `iss="autoinvoice"`. Lifetime stays 15 min.
Refresh token unchanged (`sub`, `type="refresh"`, `exp`) plus `iat`, `iss`.

`/auth/refresh` already loads the user from the DB and rejects inactive users, so
claims are rebuilt from fresh data at least every 15 minutes. Accepted trade-off:
demotion/deactivation takes effect within one access-token lifetime.

Dependencies in `app/api/deps.py`:

- `CurrentPrincipal` — decoded from token only. A small frozen dataclass
  `Principal(id, email, is_superuser, is_verified)`. No DB.
- `SuperUserDep` — built on `CurrentPrincipal` (claim check, 403 if not superuser).
- `CurrentUser` — unchanged behaviour (loads the `User` row). Kept only for routes
  that need real user fields: `/auth/me`, `/users/me*`, password endpoints,
  verify-email, Google routes, invoice send-email.

Owner-scoped routes (items, customers, invoices CRUD/stats, tables, notifications,
invoice-templates, company-settings) switch from `CurrentUser` to
`CurrentPrincipal`; they only use `.id`.

Token-in-body removal: `/auth/login`, `/auth/signup` return `{user}` only;
`/auth/refresh` returns `Message`. Cookies remain the only transport the frontend
uses. The `Authorization: Bearer` header stays accepted (Swagger / tooling).

## Google sign-in flow

1. `GET /api/v1/auth/google/login` (browser navigation, not XHR):
   - 503 if Google OAuth not configured.
   - Generate random `nonce`; set httpOnly cookie `g_oauth_nonce` (10 min,
     same secure/samesite settings as auth cookies, path `/api/v1/google`).
   - `state` = signed JWT `{type: "google_oauth_state", mode: "login", nonce, exp}`.
   - 302 to Google with scopes `openid email profile gmail.send`,
     `access_type=offline`, `prompt=consent`.
2. `GET /api/v1/google/callback` (existing redirect URI, no Google console change):
   - Decode `state`; branch on `mode` (`login` | `connect`). Existing connect
     states (no `mode`) are treated as `connect`.
   - `login` mode: require `state.nonce == cookie g_oauth_nonce`, then clear cookie.
   - Exchange code; call `https://openidconnect.googleapis.com/v1/userinfo` for
     `sub, email, email_verified, name, picture`.
   - Resolve user (`UserService.login_with_google`):
     1. user with `google_sub == sub` → that user.
     2. else user with `email == email`: if `email_verified` and `user.is_verified`
        → link (set `google_sub`); else → `LinkRequiredError`.
     3. else create user: `hashed_password=NULL`, `is_verified=True`,
        `full_name=name`, `avatar_url=picture`, `google_sub=sub`.
     - Inactive user → error.
   - Save Google tokens (existing `save_google_tokens`), set auth cookies,
     302 to `{FRONTEND_HOST}/dashboard`.
   - Errors redirect to `{FRONTEND_HOST}/login?google=<code>` where code ∈
     `error | link_required | inactive`.
3. `connect` mode (Settings "Connect Gmail", existing): additionally stores
   `google_sub`. If that `sub` belongs to a different user → redirect
   `/settings?google=already_linked`. Scopes gain `openid` (userinfo v1).

## Password rules

- `POST /auth/login` on a user with `hashed_password IS NULL` → 400
  `"This account uses Google sign-in. Continue with Google, or set a password in Settings."`
  (`authenticate` must not call `verify_password` on NULL.)
- New `POST /auth/set-password {new_password}` (CurrentUser): 400 if a password
  already exists; else validate + hash + save.
- `POST /auth/update-password` on a Google-only user → 400 pointing to set-password.
- Forgot/reset password works for Google-only users (sets first password).
- `POST /google/disconnect`: 400 if `hashed_password IS NULL`; otherwise clears
  `google_sub` and all Google token fields.

## Frontend

- `login.tsx`, `signup.tsx`: "Continue with Google" button =
  `<a href="{API_BASE}/api/v1/auth/google/login">`; read `?google=` query and show
  a toast for `error | link_required | inactive`.
- Settings security section: if `!user.has_password` show "Set a password" form
  (calls set-password) instead of "Change password".
- `GoogleIntegration.tsx`: disable Disconnect with an explanation when
  `!has_password`; handle `?google=already_linked`.
- Regenerate the OpenAPI client (`pnpm generate-client`).

## testing.html

Currently reads `access_token` from JSON bodies. Switch to cookie auth: logged-in
calls use `credentials: "include"`; each identity (test user, superuser,
throwaway) runs in sequence with a fresh login right before its calls;
unauthenticated variants use `credentials: "omit"`. Add variants for
`/auth/set-password` and `/auth/google/login` (302/503).

## Error handling

New domain errors map through existing exception handlers: `ConflictError`
(already linked) → 400, `ValidationError` → 422. OAuth callback never raises to
the user; it always redirects with a `google=` code and logs via structlog.

## Testing

Backend pytest (mock suite, Google HTTP calls mocked):
- `login_with_google`: existing sub; verified email link; unverified local refuses;
  unverified Google email refuses; new user creation; inactive user.
- Password login on Google-only user → 400 message; set-password once only;
  disconnect blocked without password.
- Principal: claims round-trip; superuser dep uses claim; owner routes work
  without DB user load.
- State/nonce: mismatched or missing nonce → `google=error`.
Plus a full testing.html run at 0% failures.
