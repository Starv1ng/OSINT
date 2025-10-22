FROM python:3.11-slim
WORKDIR /app
COPY ./services/worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY ./services/worker/tasks /app/tasks
CMD ["celery", "-A", "tasks.coordinator", "worker", "--loglevel=info", "--concurrency=1"]