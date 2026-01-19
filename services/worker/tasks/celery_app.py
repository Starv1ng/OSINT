# services/worker/tasks/celery_app.py
from celery import Celery
import os

app = Celery('osint_worker')
app.conf.update(
    broker_url='redis://redis:6379/0',
    result_backend='redis://redis:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)