from app.lambda_handler import handler


def test_function_url_trailing_slash_is_routed_not_redirected() -> None:
    # Lambda Function URLs keep the trailing slash only in rawPath.
    event = {
        "version": "2.0",
        "rawPath": "/api/v1/items/",
        "rawQueryString": "",
        "headers": {},
        "requestContext": {
            "http": {"method": "GET", "path": "/api/v1/items", "sourceIp": "1.2.3.4"}
        },
        "isBase64Encoded": False,
    }
    response = handler(event, None)
    assert response["statusCode"] == 401  # reached the route (needs auth), no 307 loop
