# services/worker/tasks/__init__.py
# Este archivo hace que la carpeta sea un paquete Python
# Intentamos importar el app de celery si está disponible; si no,
# exponemos placeholders para facilitar ejecuciones locales sin dependencias.
try:
    from .celery_app import app
except Exception as e:
    print(f"Error importing celery_app: {e}")
    app = None

try:
    from .coordinator import process_osint_job, process_osint_job_dynamic, process_osint_job_static
except Exception as e:
    print(f"Error importing coordinator: {e}")
    process_osint_job = None
    process_osint_job_dynamic = None
    process_osint_job_static = None

__all__ = ['app', 'process_osint_job', 'process_osint_job_dynamic', 'process_osint_job_static']