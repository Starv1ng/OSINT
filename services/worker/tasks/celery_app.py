# services/worker/tasks/celery_app.py
from celery import Celery
import os
from config import config

app = Celery('osint_worker')
app.conf.update(
    broker_url=config.celery.broker_url,
    result_backend=config.celery.result_backend,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)