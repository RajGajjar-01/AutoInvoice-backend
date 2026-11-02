# Findings detail (confirmed medium and above)

## AI-001-jwt-token-type-confusion: Access and refresh JWTs are interchangeable, so a short-lived access token can be refreshed indefinitely

**Severity:** medium (likelihood low, impact medium) · **Confidence:** high

Access, refresh and password-reset tokens are all HS256 JWTs signed with SECRET_KEY, and no verifier checks the token type. POST /api/v1/login/refresh accepts a 15-minute access token placed in the refresh_token cookie and mints a new access token, which can be fed back again, giving an unbounded session from one stolen access token. get_current_user also accepts a refresh token as a bearer access token, and a reset token used as a bearer token causes an unhandled 500.

**Root cause:** create_access_token emits only {exp, sub}; create_refresh_token adds refresh=True but nothing reads it. /login/refresh and get_current_user verify only signature and exp, then parse sub through TokenPayload, which declares only sub.

**Invariant:** /login/refresh accepts only refresh tokens and protected endpoints accept only access tokens, so a leaked access token expires after ACCESS_TOKEN_EXPIRE_MINUTES and sessions are bounded by REFRESH_TOKEN_EXPIRE_DAYS.

### Trace
1. `entrypoint` `app/api/routes/login.py:84` (refresh_token (POST /api/v1/login/refresh)): Reads the client-controlled refresh_token cookie.
2. `propagation` `app/api/routes/login.py:100` (refresh_token): jwt.decode checks only signature and exp; the refresh claim is never checked and TokenPayload keeps only sub.
3. `propagation` `app/api/routes/login.py:111` (refresh_token): Only user existence and is_active are checked.
4. `sink` `app/api/routes/login.py:118` (refresh_token): A fresh access token is minted and returned; it can be resubmitted as refresh_token without limit.

### Evidence
- `app/core/security.py:24`: Access token claims are only {exp, sub}, signed with the same key and algorithm as refresh tokens.
- `app/core/security.py:36`: Refresh token adds refresh=True, but no verifier reads it.
- `app/api/deps.py:49`: get_current_user decodes any JWT without a type check (harness C1: refresh token accepted as bearer, 200).
- `app/models.py:123`: TokenPayload declares only sub, so type claims are dropped.
- `app/utils.py:109`: Reset token uses the same key with sub=email and no type claim; used as bearer it returns 500 (harness C9).

### Conditions
- authentication_level: The attacker must already hold one valid, unexpired access token for the victim.
- data_state: The victim account must still exist and be active.

### Bounded local reproduction (dummy principals only)
Attacker: An attacker who briefly obtained a victim's 15-minute access token and wants to keep the session past its expiry.

```
POST /api/v1/login/refresh with Cookie: refresh_token=<victim access_token JWT>
```
```
POST /api/v1/login/refresh with Cookie: refresh_token=<access_token returned by the previous refresh>
```

1. Log in as a dummy victim and take access_token from the JSON body.
2. Send POST /api/v1/login/refresh with that access token in the refresh_token cookie.
3. Observe 200 and a new access_token; repeat before each expiry to keep the session alive indefinitely.

**Observed:** Sandboxed local harness (agents/parent-hunter/artifacts/poc-baseline.json): C2 access-as-refresh returned 200 with a minted token; C1 refresh-as-bearer returned 200 as the victim; C9 reset-as-bearer returned 500. After the fix (agents/parent-fixcheck/artifacts/poc-fixed.json) C1, C2 and C9 return 403.

### Remediation
Add an explicit type claim (access/refresh/password_reset) plus iat/nbf/jti to every token, require exp/iat/sub/type at decode, and enforce the expected type in each verifier through one decode_token helper. Rotate the refresh token on use. Regression tests: tests/api/routes/test_security.py::test_refresh_token_rejected_as_access_token, test_access_token_rejected_as_refresh_token, test_reset_token_rejected_as_access_token.

## AI-002-no-token-revocation-on-credential-change: Access and refresh tokens stay valid after password change, password reset and logout

**Severity:** medium (likelihood low, impact medium) · **Confidence:** high

Sessions are stateless JWTs with no server-side binding to the user's credentials. Changing or resetting the password only replaces hashed_password, and logout only deletes browser cookies, so previously issued access tokens (15 min) and refresh tokens (7 days, unbounded with AI-001) keep working. An attacker holding stolen tokens survives the victim's password rotation.

**Root cause:** Tokens carry only sub/exp, and get_current_user and /login/refresh check only that the user exists and is active. Nothing binds a token to a credential version, so password change, reset and logout cannot invalidate issued tokens.

**Invariant:** Password change, password reset and logout invalidate previously issued access and refresh tokens.

### Trace
1. `entrypoint` `app/api/routes/users.py:102` (update_password_me (PATCH /api/v1/users/me/password)): The victim changes their password to recover from compromise.
2. `propagation` `app/api/routes/users.py:117` (update_password_me): Only hashed_password is replaced; no token version or denylist is updated.
3. `propagation` `app/api/routes/login.py:111` (refresh_token): Old refresh tokens are validated only by user existence and is_active.
4. `sink` `app/api/routes/login.py:118` (refresh_token): A new access token is minted for the holder of the pre-change refresh token.

### Evidence
- `app/api/deps.py:58`: get_current_user authorizes any validly signed token for an existing active user, with no credential-version comparison.
- `app/api/routes/login.py:186`: reset_password updates only the password through crud.update_user.
- `app/api/routes/login.py:139`: logout only deletes cookies; the tokens stay valid server-side.

### Conditions
- authentication_level: The attacker previously obtained the victim's access or refresh token.
- user_interaction: The victim changes or resets the password, or logs out, expecting other sessions to end.

### Bounded local reproduction (dummy principals only)
Attacker: An attacker holding a victim's stolen tokens after the victim rotates the password.

```
PATCH /api/v1/users/me/password {"current_password":"victim-pass-123","new_password":"victim-pass-456"}
```
```
GET /api/v1/users/me with Authorization: Bearer <pre-change access_token>
```
```
POST /api/v1/login/refresh with Cookie: refresh_token=<pre-change refresh_token>
```

1. Log in as a dummy victim and record both tokens.
2. Change the victim's password.
3. Reuse the old access token at /users/me and the old refresh token at /login/refresh.

**Observed:** Sandboxed harness C3 (poc-baseline.json): both returned 200 after the password change. After the fix (poc-fixed.json) both return 403.

### Remediation
Add an integer token_version column to User (Alembic migration b7c1d2e3f4a5), embed it as the ver claim in access and refresh tokens, reject tokens whose ver differs from the user's current value, and increment it on password change, password reset, logout, and admin changes to email, password, is_active or is_superuser. Regression tests: test_tokens_revoked_after_password_change, test_tokens_revoked_after_logout, test_reset_password_revokes_sessions.

## AI-003-reset-token-replay: Password-reset tokens are reusable for 48 hours and survive the reset they authorize

**Severity:** medium (likelihood low, impact high) · **Confidence:** high

The reset token is a stateless JWT valid for 48 hours. POST /api/v1/reset-password/ records no use and the token is not bound to the current password hash, so after the legitimate user resets, the same link still works for the rest of the window. Anyone who later sees the link (mailbox, browser history, logs) can set a new password and take over the account.

**Root cause:** generate_password_reset_token includes no single-use binding, and verify_password_reset_token and reset_password have no server-side state that a completed reset would change.

**Invariant:** A reset token authorizes exactly one password change, becomes invalid once the password changes, and expires after a short window.

### Trace
1. `entrypoint` `app/api/routes/login.py:172` (reset_password (POST /api/v1/reset-password/)): An unauthenticated caller submits {token, new_password}.
2. `propagation` `app/api/routes/login.py:177` (reset_password): verify_password_reset_token checks only signature and expiry and returns sub=email.
3. `sink` `app/api/routes/login.py:187` (reset_password): crud.update_user overwrites hashed_password with the caller-chosen password; this can happen again with the same token.

### Evidence
- `app/utils.py:109`: Reset token claims are only exp, nbf and sub=email.
- `app/core/config.py:86`: EMAIL_RESET_TOKEN_EXPIRE_HOURS = 48.
- `app/utils.py:71`: The token travels in a URL query string, so it persists in mail and browser history.

### Conditions
- user_interaction: The victim requested a reset, so a valid token was emailed.
- data_state: The attacker obtains the used link within its validity window.

### Bounded local reproduction (dummy principals only)
Attacker: An unauthenticated attacker who obtains a victim's already-used reset link.

```
POST /api/v1/reset-password/ {"token":"<reset JWT>","new_password":"attacker-set-1"}
```
```
POST /api/v1/reset-password/ {"token":"<same reset JWT>","new_password":"attacker-set-2"}
```

1. Generate a reset token for a dummy victim as /password-recovery does.
2. Submit it once (the victim's legitimate reset).
3. Submit the same token again with a different password.

**Observed:** Sandboxed harness C4 (poc-baseline.json): first=200, second=200, and the attacker's password then logged in. After the fix (poc-fixed.json): first=200, second=400.

### Remediation
Bind the reset token to an HMAC fingerprint of the user's current password hash (pwd claim), give it type=password_reset and sub=user id, compare the fingerprint with hmac.compare_digest before resetting, shorten EMAIL_RESET_TOKEN_EXPIRE_HOURS to 1, and revoke sessions on reset. Regression test: test_reset_token_is_single_use.

## AI-010-email-change-without-reauth: Account email can be changed with only a bearer token, letting a token thief take over the account through password recovery

**Severity:** medium (likelihood low, impact high) · **Confidence:** medium

PATCH /api/v1/users/me accepted a new email with only a uniqueness check, with no current password and no ownership verification, while PATCH /users/me/password does require the current password. Someone holding a victim's access token could switch the email to an address they control, then use password recovery to set a new password. The victim is permanently locked out.

**Root cause:** update_user_me applied user_in.model_dump(exclude_unset=True), including email, directly to current_user without re-authentication, and password recovery trusts the stored email as the recovery channel.

**Invariant:** Changing the account's login and recovery identifier requires the same proof as changing the password (the current password).

### Trace
1. `entrypoint` `app/api/routes/users.py:80` (update_user_me): PATCH /users/me, authenticated only by CurrentUser.
2. `propagation` `app/api/routes/users.py:95` (update_user_me): The body-supplied email is written and committed.
3. `propagation` `app/api/routes/login.py:153` (recover_password): Unauthenticated recovery looks up the new email and mails a reset token to it.
4. `sink` `app/api/routes/login.py:187` (reset_password): The attacker's chosen password replaces the victim's credentials.

### Evidence
- `app/api/routes/users.py:109`: update_password_me requires the current password, so the application's own re-authentication rule is skipped for email changes.
- `app/utils.py:39`: send_email requires SMTP to be configured for the recovery step.

### Conditions
- authentication_level: The attacker holds a valid access token for the victim.
- system_configuration: SMTP is configured so password recovery sends mail.

### Bounded local reproduction (dummy principals only)
Attacker: A token thief who does not know the victim's password and controls attacker@example.test.

```
PATCH /api/v1/users/me {"email":"attacker@example.test"} with Authorization: Bearer <victim token>
```
```
POST /api/v1/password-recovery/attacker@example.test
```
```
POST /api/v1/reset-password/ {"token":"<emailed token>","new_password":"AttackerChosen123"}
```

1. PATCH the victim's email using only the token.
2. Request password recovery for the new address.
3. Reset the password using the emailed token.

**Observed:** Established by an independent source trace only, with no local run of the full chain (SMTP is not available in the sandbox). After the fix, tests/api/routes/test_users.py::test_update_user_me_email_requires_current_password shows the email change is refused (400) without the correct current password.

### Remediation
Require current_password on PATCH /users/me whenever the email changes, normalize email case, and log the change. A follow-up should send a confirmation to the new address and a notice to the old one.
