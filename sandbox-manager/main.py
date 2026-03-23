import logging

import uvicorn
from fastapi import FastAPI

from router import healthcheck, sandbox_router, ui_router
from util.lifespan_handlers import lifespan
from config.settings import app_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

app = FastAPI(lifespan=lifespan)

app.include_router(healthcheck.router)
app.include_router(sandbox_router.router)
app.include_router(ui_router.router)

if __name__ == "__main__":
    uvicorn.run(app, host=app_settings.host, port=app_settings.port,
                limit_concurrency=app_settings.app_limit_concurrency, backlog=app_settings.app_backlog,
                timeout_keep_alive=app_settings.app_timeout_keep_alive, log_level="info")
