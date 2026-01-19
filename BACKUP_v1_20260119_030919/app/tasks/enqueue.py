# services/api/app/tasks/enqueue.py
from celery import Celery
import logging
import os

# Configurar Celery para el API (debe usar la misma configuración)
celery_app = Celery('api_sender')
celery_app.conf.update(
    broker_url='redis://redis:6379/0',
    result_backend='redis://redis:6379/0',
)

logger = logging.getLogger(__name__)


def enqueue_job(job_id, payload):
    """Encolar job para procesamiento"""
    logger.info(f"[API] Encolando trabajo: {job_id}")

    # Enviar tarea usando el MISMO nombre de task
    result = celery_app.send_task(
        'process_osint_job',  # Mismo nombre que en el worker
        args=[job_id, payload],
        queue='celery'
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "task_id": result.id
    }