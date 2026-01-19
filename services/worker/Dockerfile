# services/worker/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY ./services/worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY ./services/worker/tasks /app

# CAMBIAR EL CMD (usar 'tasks' como módulo)
CMD ["celery", "-A", "tasks", "worker", "--loglevel=info", "--concurrency=1"]