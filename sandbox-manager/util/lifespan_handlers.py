import logging
from contextlib import asynccontextmanager
from urllib.parse import quote_plus

from fastapi import FastAPI
from pymongo import MongoClient

from config.settings import app_settings
from router.sandbox_router import file_queue, queued_ids

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_handler(app)
    yield
    shutdown_handler(app)


def startup_handler(app: FastAPI) -> None:
    app.state.manager_state = "STARTED"
    app.mongodb_client = MongoClient(
        f"mongodb://{quote_plus(app_settings.mongo_username)}:{quote_plus(app_settings.mongo_password)}@{app_settings.mongo_host}"
    )
    app.database = app.mongodb_client[app_settings.mongo_db]

    file_queue.queue.clear()
    queued_ids.clear()

    # On restart, recover both QUEUED tasks and PROCESSING tasks.
    # PROCESSING tasks were being handled by a worker that is now gone,
    # so they are reset to QUEUED and re-enqueued.
    recovering = list(app.database["malware_queue"].find(
        {"status": {"$in": ["QUEUED", "PROCESSING"]}}
    ))
    for item in recovering:
        if item["status"] == "PROCESSING":
            app.database["malware_queue"].update_one(
                {"_id": item["_id"]},
                {"$set": {"status": "QUEUED", "worker_id": None}}
            )
        file_queue.put((item["path"], item["_id"]))
        queued_ids.add(item["_id"])

    logger.info(f"Connected to MongoDB — recovered {len(recovering)} task(s) into queue")


def shutdown_handler(app: FastAPI) -> None:
    app.mongodb_client.close()
