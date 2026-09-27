from unittest.mock import patch

from fastapi import Response

from app.core import auth_cookies


def test_clear_auth_cookies_matches_cross_site_attributes() -> None:
    # Cookies set as SameSite=None; Secure (frontend and API on different sites)
    # are only removed if the deletion carries the same attributes.
    response = Response()
    with (
        patch.object(auth_cookies, "COOKIE_SECURE", True),
        patch.object(auth_cookies, "COOKIE_SAMESITE", "none"),
    ):
        auth_cookies.clear_auth_cookies(response)
    cookies = response.headers.getlist("set-cookie")
    assert len(cookies) == 2
    for cookie in cookies:
        assert "Max-Age=0" in cookie
        assert "Secure" in cookie
        assert "SameSite=none" in cookie
        assert "HttpOnly" in cookie
