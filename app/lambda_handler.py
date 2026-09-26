from mangum import Mangum

from app.main import app

# Mangum waits for the ASGI app to finish, so BackgroundTasks (emails) complete
# before Lambda freezes the environment. The app defines no lifespan.
handler = Mangum(app, lifespan="off")
