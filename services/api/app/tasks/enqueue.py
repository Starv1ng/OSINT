# services/api/app/tasks/enqueue.py
from celery import Celery
import os

CELERY_BROKER = os.environ.get("CELERY_BROKER", "redis://redis:6379/0")
celery_app = Celery("api_enqueue", broker=CELERY_BROKER)

@celery_app.task
def enqueue_job(job_id, payload):
    # Este task se delega al worker real
    return {"job_id": job_id, "status": "enqueued"}