from fastapi import FastAPI
from contextlib import asynccontextmanager
import socket


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_handler(app)
    yield
    shutdown_handler(app)


def startup_handler(app: FastAPI) -> None:
    app.state.worker={}
    app.state.worker["state"] = "WAITING_FOR_TASK"
    # To find the host ip address of the worker instance
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    app.state.worker["worker_ip"] = s.getsockname()[0]
    s.close()



def shutdown_handler(app: FastAPI) -> None:
    pass
