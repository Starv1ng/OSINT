# services/api/app/api/routes.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import uuid
from api.auth import get_current_user
from api.models.db import get_session
from sqlalchemy import text

router = APIRouter()

class IngestRequest(BaseModel):
    input_type: str
    value: str
    requester_id: str
    priority_countries: list[str] = []
    max_depth: int = 1

@router.post("/ingest/name", status_code=202)
def ingest_name(req: IngestRequest, user=Depends(get_current_user)):
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    session = get_session()
    try:
        # Usar SQL directo en lugar de SQLAlchemy Core para simplificar
        query = text("""
            INSERT INTO jobs (job_id, requester_id, input_type, input_value, status)
            VALUES (:job_id, :requester_id, :input_type, :input_value, :status)
        """)
        session.execute(query, {
            "job_id": job_id,
            "requester_id": req.requester_id,
            "input_type": req.input_type,
            "input_value": req.value,
            "status": "accepted"
        })
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        session.close()
    
    # Encolar tarea Celery (simulada por ahora)
    # from api.tasks.enqueue import enqueue_job
    # enqueue_job.delay(job_id, req.dict())
    
    return {"job_id": job_id, "status": "accepted"}

@router.get("/health")
def health_check():
    return {"status": "healthy", "service": "OSINT API"}