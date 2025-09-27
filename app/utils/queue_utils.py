from app.celery_app import celery_app
from celery.result import AsyncResult
import logging

logger = logging.getLogger("queue_utils")

def get_task_status(task_id: str) -> str:
    result = AsyncResult(task_id, app=celery_app)
    return result.status

def get_task_result(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    if result.ready():
        return result.result
    return None

def get_queue_health() -> dict:
    insp = celery_app.control.inspect()
    stats = insp.stats() or {}
    active = insp.active() or {}
    reserved = insp.reserved() or {}
    return {"stats": stats, "active": active, "reserved": reserved}

def cleanup_queue():
    # Example: Purge all tasks (use with caution!)
    celery_app.control.purge()
    logger.info("Queue purged.") 