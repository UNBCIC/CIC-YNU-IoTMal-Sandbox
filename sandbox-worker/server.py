import uvicorn
from fastapi import FastAPI

from router import healthcheck, sandbox_router
from util.lifespan_handlers import lifespan
from config.settings import app_settings

app = FastAPI(lifespan=lifespan)


# Add Routers here.
app.include_router(healthcheck.router)
app.include_router(sandbox_router.router)


if __name__ == "__main__":
    uvicorn.run(app, host=app_settings.host, port=app_settings.port,
                limit_concurrency=app_settings.app_limit_concurrency, backlog=app_settings.app_backlog,
                timeout_keep_alive=app_settings.app_timeout_keep_alive, log_level="info")
