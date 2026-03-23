import logging
import os
import queue
import shutil
import urllib.request
import uuid

from fastapi import APIRouter, Request, UploadFile, HTTPException
from starlette.responses import FileResponse

from config.settings import app_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix=app_settings.app_base_url)

file_queue = queue.Queue()
queued_ids: set = set()  # in-memory duplicate guard — mirrors what is currently in file_queue


def _enqueue(db, task_id: str, file_path: str, filename: str):
    """Add a task to the in-memory queue and upsert it in the database.
    No-op if the task_id is already queued."""
    if task_id in queued_ids:
        return
    file_queue.put((file_path, task_id))
    queued_ids.add(task_id)
    db["malware_queue"].update_one(
        {"_id": task_id},
        {"$set": {"_id": task_id, "filename": filename, "path": file_path, "status": "QUEUED"}},
        upsert=True
    )


@router.get("/status")
async def get_status(request: Request):
    """Return task counts grouped by status and the current in-memory queue depth."""
    pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    counts = {
        doc["_id"]: doc["count"]
        for doc in request.app.database["malware_queue"].aggregate(pipeline)
    }
    return {
        "queued": counts.get("QUEUED", 0),
        "processing": counts.get("PROCESSING", 0),
        "completed": counts.get("COMPLETED", 0),
        "failed": counts.get("FAILED", 0),
        "cancelled": counts.get("CANCELLED", 0),
        "in_memory_queue": file_queue.qsize(),
    }


@router.get("/init-queue")
async def init_queue(request: Request):
    """Scan the malware directory and enqueue any files not already tracked."""
    if not os.path.exists(app_settings.malware_directory):
        logger.error(f"Malware directory not found: {app_settings.malware_directory}")
        raise HTTPException(status_code=500, detail='Malware directory not found')

    malware_dir = os.path.realpath(app_settings.malware_directory)
    all_files = []
    for dirpath, _, filenames in os.walk(malware_dir):
        for f in filenames:
            full_path = os.path.join(dirpath, f)
            if os.path.realpath(full_path).startswith(malware_dir + os.sep):
                all_files.append((full_path, f))

    added = 0
    skipped = 0
    for file_path, filename in all_files:
        # Skip if this path is already actively queued or being processed
        existing = request.app.database["malware_queue"].find_one(
            {"path": file_path, "status": {"$in": ["QUEUED", "PROCESSING"]}}
        )
        if existing:
            skipped += 1
            continue
        _enqueue(request.app.database, str(uuid.uuid4()), file_path, filename)
        added += 1

    logger.info(f"Queue initialised: {added} added, {skipped} skipped")
    return {"added": added, "skipped": skipped, "total": len(all_files)}


@router.post("/submit-file")
async def submit_file(request: Request, file: UploadFile):
    """Submit a single malware binary directly for analysis."""
    task_id = str(uuid.uuid4())
    os.makedirs(app_settings.upload_dir, exist_ok=True)
    file_path = os.path.join(app_settings.upload_dir, task_id)
    try:
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to save uploaded file')
    finally:
        file.file.close()

    _enqueue(request.app.database, task_id, file_path, file.filename)
    logger.info(f"Submitted file '{file.filename}' as task {task_id}")
    return {"task_id": task_id, "filename": file.filename, "status": "QUEUED"}


@router.get("/get-file/{worker_id}")
async def get_file(request: Request, worker_id: str, worker_uri: str = ""):
    """Hand the next queued task to a worker."""
    try:
        file_path, task_id = file_queue.get(block=False)
        queued_ids.discard(task_id)
        request.app.database["malware_queue"].update_one(
            {"_id": task_id},
            {"$set": {"status": "PROCESSING", "worker_id": str(worker_id), "worker_uri": worker_uri}}
        )
        logger.info(f"Dispatching task {task_id} to worker {worker_id}")
        return FileResponse(file_path, media_type='application/octet-stream', filename=task_id)
    except queue.Empty:
        raise HTTPException(status_code=404, detail='No tasks available')


@router.post("/submit-result/{task_id}")
async def submit_result(request: Request, task_id: str, file: UploadFile):
    """Receive the completed analysis result zip from a worker."""
    result_path = os.path.join(app_settings.output_dir, task_id + ".zip")
    try:
        with open(result_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)
        request.app.database["malware_queue"].update_one(
            {"_id": task_id},
            {"$set": {"status": "COMPLETED", "result_path": result_path}}
        )
    except Exception:
        raise HTTPException(status_code=500, detail='Something went wrong')
    finally:
        file.file.close()
    logger.info(f"Received result for task: {task_id}")
    return {"task_id": task_id, "status": "COMPLETED"}


@router.post("/submit-failure/{task_id}")
async def submit_failure(request: Request, task_id: str, reason: str = ""):
    """Mark a task as FAILED. Called by a worker when analysis throws an unrecoverable error."""
    result = request.app.database["malware_queue"].update_one(
        {"_id": task_id},
        {"$set": {"status": "FAILED", "failure_reason": reason}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail='Task not found')
    logger.warning(f"Task {task_id} marked FAILED: {reason}")
    return {"task_id": task_id, "status": "FAILED"}


@router.post("/cancel/{task_id}")
async def cancel_task(request: Request, task_id: str):
    """Cancel a PROCESSING task. Marks it CANCELLED and signals the worker to stop."""
    task = request.app.database["malware_queue"].find_one({"_id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    if task.get("status") != "PROCESSING":
        raise HTTPException(status_code=400, detail='Task is not currently being processed')

    request.app.database["malware_queue"].update_one(
        {"_id": task_id},
        {"$set": {"status": "CANCELLED"}}
    )
    logger.info(f"Task {task_id} marked CANCELLED")

    worker_uri = task.get("worker_uri", "")
    if worker_uri:
        try:
            urllib.request.urlopen(worker_uri + "/stop", data=b'', timeout=3)
        except Exception:
            logger.warning(f"Could not reach worker to stop task {task_id}")

    return {"task_id": task_id, "status": "CANCELLED"}


@router.get("/tasks")
async def list_tasks(request: Request, status: str = None):
    """List all tasks, optionally filtered by status (QUEUED, PROCESSING, COMPLETED, FAILED)."""
    query = {"status": status.upper()} if status else {}
    tasks = list(request.app.database["malware_queue"].find(
        query,
        {"_id": 1, "filename": 1, "status": 1, "worker_id": 1, "failure_reason": 1}
    ))
    return {
        "tasks": [
            {
                "task_id": t["_id"],
                "filename": t.get("filename", ""),
                "status": t.get("status", ""),
                "worker_id": t.get("worker_id", ""),
                "failure_reason": t.get("failure_reason", ""),
            }
            for t in tasks
        ]
    }


@router.get("/results")
async def list_results(request: Request):
    """List all completed analysis tasks."""
    completed = list(request.app.database["malware_queue"].find(
        {"status": "COMPLETED"},
        {"_id": 1, "filename": 1, "worker_id": 1}
    ))
    return {
        "results": [
            {"task_id": r["_id"], "filename": r.get("filename", ""), "worker_id": r.get("worker_id", "")}
            for r in completed
        ]
    }


@router.get("/results/{task_id}")
async def get_result(task_id: str):
    """Download the analysis result zip for a completed task."""
    result_path = os.path.join(app_settings.output_dir, task_id + ".zip")
    if not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail='Result not found')
    return FileResponse(result_path, media_type='application/zip', filename=task_id + ".zip")
