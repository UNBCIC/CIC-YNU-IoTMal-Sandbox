import concurrent.futures
import shutil
import os
from fastapi import APIRouter, Request, UploadFile, HTTPException
from starlette.responses import FileResponse
from functools import partial

from config.settings import app_settings
from service.analysis import dynamic_analysis, request_stop

router = APIRouter(prefix=app_settings.app_base_url)


@router.post("/submit-task/{task_id}")
async def submit_task(request: Request, task_id: str, file: UploadFile):
    try:
        os.makedirs(app_settings.data_dir + task_id)
        with open(app_settings.data_dir + task_id + "/" + task_id, 'wb') as f:
            shutil.copyfileobj(file.file, f)
    except Exception:
        raise HTTPException(status_code=500, detail='Something went wrong')
    finally:
        file.file.close()
    executor = concurrent.futures.ProcessPoolExecutor()
    executor.submit(partial(dynamic_analysis, task_id, task_dir=app_settings.data_dir + task_id, worker=request.app.state.worker))
    return {"task_id": task_id, "status": "TASK_RECEIVED"}


@router.get("/get-task/{task_id}/file")
async def get_task_file(task_id: str):
    file_path = app_settings.data_dir + task_id + "/" + task_id
    return FileResponse(file_path, media_type='application/octet-stream', filename=task_id)


@router.post("/update-task/{task_id}/strace")
async def update_strace(task_id: str, file: UploadFile):
    try:
        with open(app_settings.data_dir + task_id + "/strace.log", 'wb') as f:
            shutil.copyfileobj(file.file, f)
    except Exception:
        raise HTTPException(status_code=500, detail='Something went wrong')
    finally:
        file.file.close()
    return {"task_id": task_id, "status": "RECEIVED"}


@router.post("/stop")
async def stop_analysis():
    """Signal the running analysis to stop. The poller will clean up and report CANCELLED."""
    request_stop()
    return {"status": "stop requested"}


@router.post("/update-task/{task_id}/sar")
async def update_sar(task_id: str, file: UploadFile):
    try:
        with open(app_settings.data_dir + task_id + "/sar.out", 'wb') as f:
            shutil.copyfileobj(file.file, f)
    except Exception:
        raise HTTPException(status_code=500, detail='Something went wrong')
    finally:
        file.file.close()
    return {"task_id": task_id, "status": "RECEIVED"}
