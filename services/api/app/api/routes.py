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
    
    return {"job_id": job_id, "status": "accepted"}

@router.get("/health")
def health_check():
    return {"status": "healthy", "service": "OSINT API"}

@router.get("/test-db")
def test_db_connection():
    """Endpoint para probar conexión a la base de datos"""
    try:
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
        return {"database": "connected", "status": "healthy"}
    except Exception as e:
        return {"database": "error", "status": "unhealthy", "error": str(e)}