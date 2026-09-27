from typing import Any

from mangum import Mangum

from app.main import app

# Mangum waits for the ASGI app to finish, so BackgroundTasks (emails) complete
# before Lambda freezes the environment. The app defines no lifespan.
_mangum = Mangum(app, lifespan="off")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    # Function URLs drop the trailing slash from requestContext.http.path (which
    # Mangum routes on) but keep it in rawPath; without this, "/items/" routes
    # redirect to themselves forever.
    http = event.get("requestContext", {}).get("http")
    if http and event.get("rawPath"):
        http["path"] = event["rawPath"]
    return _mangum(event, context)
