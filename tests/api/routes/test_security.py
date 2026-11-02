"""Regression tests for the security audit findings (AI-001 .. AI-009)."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core import security
from app.core.config import settings
from app.core.rate_limit import limiter
from app.main import app
from app.models import UserCreate
from app.utils import generate_password_reset_token
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR
REFRESH_PATH = f"{API}/login/refresh"


def _new_user(db: Session) -> tuple[str, str]:
    email = random_email()
    password = random_lower_string()
    crud.create_user(session=db, user_create=UserCreate(email=email, password=password))
    return email, password


def _login(email: str, password: str) -> tuple[TestClient, str, str]:
    c = TestClient(app)
    r = c.post(
        f"{API}/login/access-token", data={"username": email, "password": password}
    )
    assert r.status_code == 200
    return c, r.json()["access_token"], r.cookies["refresh_token"]


def test_refresh_token_rejected_as_access_token(db: Session) -> None:
    _, _, refresh = _login(*_new_user(db))
    r = TestClient(app).get(
        f"{API}/users/me", headers={"Authorization": f"Bearer {refresh}"}
    )
    assert r.status_code == 403


def test_access_token_rejected_as_refresh_token(db: Session) -> None:
    _, access, _ = _login(*_new_user(db))
    c = TestClient(app)
    c.cookies.set("refresh_token", access, path=REFRESH_PATH)
    r = c.post(REFRESH_PATH, headers={"Origin": settings.FRONTEND_HOST})
    assert r.status_code == 403


def test_reset_token_rejected_as_access_token(db: Session) -> None:
    email, _ = _new_user(db)
    user = crud.get_user_by_email(session=db, email=email)
    assert user
    token = generate_password_reset_token(user=user)
    r = TestClient(app).get(
        f"{API}/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 403


def test_refresh_works_and_rotates(db: Session) -> None:
    c, _, refresh = _login(*_new_user(db))
    r = c.post(REFRESH_PATH, headers={"Origin": settings.FRONTEND_HOST})
    assert r.status_code == 200
    assert r.json()["access_token"]
    assert r.cookies.get("refresh_token") and r.cookies["refresh_token"] != refresh


def test_tokens_revoked_after_password_change(db: Session) -> None:
    email, password = _new_user(db)
    _, access, refresh = _login(email, password)
    r = TestClient(app).patch(
        f"{API}/users/me/password",
        headers={"Authorization": f"Bearer {access}"},
        json={"current_password": password, "new_password": random_lower_string()},
    )
    assert r.status_code == 200
    r = TestClient(app).get(
        f"{API}/users/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert r.status_code == 403
    c = TestClient(app)
    c.cookies.set("refresh_token", refresh, path=REFRESH_PATH)
    assert (
        c.post(REFRESH_PATH, headers={"Origin": settings.FRONTEND_HOST}).status_code
        == 403
    )


def test_tokens_revoked_after_logout(db: Session) -> None:
    _, access, _ = _login(*_new_user(db))
    headers = {"Authorization": f"Bearer {access}"}
    assert (
        TestClient(app).post(f"{API}/login/logout", headers=headers).status_code == 200
    )
    assert TestClient(app).get(f"{API}/users/me", headers=headers).status_code == 403


def test_reset_token_is_single_use(db: Session) -> None:
    email, _ = _new_user(db)
    user = crud.get_user_by_email(session=db, email=email)
    assert user
    token = generate_password_reset_token(user=user)
    c = TestClient(app)
    r1 = c.post(
        f"{API}/reset-password/",
        json={"token": token, "new_password": random_lower_string()},
    )
    r2 = c.post(
        f"{API}/reset-password/",
        json={"token": token, "new_password": random_lower_string()},
    )
    assert r1.status_code == 200
    assert r2.status_code == 400


def test_reset_password_revokes_sessions(db: Session) -> None:
    email, password = _new_user(db)
    _, access, _ = _login(email, password)
    user = crud.get_user_by_email(session=db, email=email)
    assert user
    token = generate_password_reset_token(user=user)
    r = TestClient(app).post(
        f"{API}/reset-password/",
        json={"token": token, "new_password": random_lower_string()},
    )
    assert r.status_code == 200
    r = TestClient(app).get(
        f"{API}/users/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert r.status_code == 403


def test_expired_token_rejected(db: Session) -> None:
    email, _ = _new_user(db)
    user = crud.get_user_by_email(session=db, email=email)
    assert user
    token = security.create_access_token(
        user.id, timedelta(seconds=-1), user.token_version
    )
    r = TestClient(app).get(
        f"{API}/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 403


def test_login_is_throttled_after_repeated_failures(db: Session) -> None:
    email, password = _new_user(db)
    settings.RATE_LIMIT_ENABLED = True
    limiter.reset()
    c = TestClient(app)
    codes = [
        c.post(
            f"{API}/login/access-token",
            data={"username": email, "password": f"wrong-{i}-xx"},
        ).status_code
        for i in range(settings.LOGIN_MAX_FAILED_ATTEMPTS)
    ]
    assert set(codes) == {400}
    # Even the correct password is refused while locked out.
    r = c.post(
        f"{API}/login/access-token", data={"username": email, "password": password}
    )
    assert r.status_code == 429


def test_password_recovery_is_throttled() -> None:
    settings.RATE_LIMIT_ENABLED = True
    limiter.reset()
    c = TestClient(app)
    email = random_email()
    codes = [
        c.post(f"{API}/password-recovery/{email}").status_code
        for _ in range(settings.PASSWORD_RECOVERY_RATE_LIMIT_PER_EMAIL + 1)
    ]
    assert codes[-1] == 429


def test_signup_does_not_reveal_existing_accounts(db: Session) -> None:
    email, _ = _new_user(db)
    c = TestClient(app)
    existing = c.post(
        f"{API}/users/signup", json={"email": email, "password": random_lower_string()}
    )
    fresh = c.post(
        f"{API}/users/signup",
        json={"email": random_email(), "password": random_lower_string()},
    )
    assert existing.status_code == fresh.status_code == 200
    assert existing.json() == fresh.json()


def test_cookie_auth_requires_trusted_origin(db: Session) -> None:
    c, _, _ = _login(*_new_user(db))
    body = {"title": "csrf"}
    assert c.post(f"{API}/items/", json=body).status_code == 403
    assert (
        c.post(
            f"{API}/items/", json=body, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    r = c.post(f"{API}/items/", json=body, headers={"Origin": settings.FRONTEND_HOST})
    assert r.status_code == 200
    # Safe methods do not need an Origin.
    assert c.get(f"{API}/users/me").status_code == 200


def test_bearer_header_takes_precedence_over_cookie(db: Session) -> None:
    a_email, a_pw = _new_user(db)
    b_email, b_pw = _new_user(db)
    c, _, _ = _login(a_email, a_pw)
    _, b_access, _ = _login(b_email, b_pw)
    r = c.get(f"{API}/users/me", headers={"Authorization": f"Bearer {b_access}"})
    assert r.json()["email"] == b_email


def test_security_headers_present() -> None:
    r = TestClient(app).get(f"{API}/utils/health-check/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]


def test_settings_reject_weak_secret_outside_local(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import pytest

    from app.core.config import Settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "changethis")
    with pytest.raises(ValueError):
        Settings(_env_file=None)  # type: ignore[call-arg]
    monkeypatch.setenv("SECRET_KEY", "short")
    with pytest.raises(ValueError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_environment_defaults_to_production(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import Settings

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.setenv("POSTGRES_PASSWORD", "not-default-pw")
    monkeypatch.setenv("FIRST_SUPERUSER_PASSWORD", "not-default-pw")
    assert Settings(_env_file=None).ENVIRONMENT == "production"  # type: ignore[call-arg]
