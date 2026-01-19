# services/api/app/api/routes.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import uuid
from api.auth import get_current_user
from api.models.db import get_session
from tasks.es_client import get_findings, get_module_runs
import logging

logger = logging.getLogger(__name__)
from sqlalchemy import text
from tasks.enqueue import enqueue_job  # ← Función normal, NO task Celery
from datetime import datetime

router = APIRouter()

class IngestRequest(BaseModel):
    input_type: str = "auto"
    value: str
    requester_id: str = "web_user"
    priority_countries: list[str] = []
    max_depth: int = 1

@router.post("/ingest/name", status_code=202)
def ingest_name(req: IngestRequest, user=Depends(get_current_user)):
    """
    Endpoint para registrar una nueva búsqueda OSINT.
    """
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    session = get_session()

    try:
        # 1. Guardar en base de datos
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

        # 2. Encolar el trabajo - llamada directa sin .delay()
        logger.info(f"[API] Encolando trabajo: {job_id}")
        enqueue_result = enqueue_job(job_id, req.dict())  # ← SIN .delay()

        return {
            "job_id": job_id,
            "status": "accepted",
            "task_id": enqueue_result.get("task_id")  # ← Info adicional útil
        }

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        session.close()

@router.get("/jobs/{job_id}")
def get_job_status(job_id: str, user=Depends(get_current_user)):
    """
    Consultar estado y resultados de un trabajo.
    """
    session = get_session()
    try:
        query = text("""
            SELECT job_id, status, result, created_at, updated_at, input_type
            FROM jobs WHERE job_id = :job_id
        """)
        result = session.execute(query, {"job_id": job_id}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Job not found")

        # Respuesta base desde Postgres (estado y marcas de tiempo)
        reply = {
            "job_id": result[0],
            "status": result[1],
            "result": result[2] if result[2] else None,
            "created_at": result[3].isoformat() if result[3] else None,
            "updated_at": result[4].isoformat() if result[4] else None,
            "input_type": result[5] if result[5] else None
        }

        # Si el trabajo está completado o no tiene resultados en línea, intentar enriquecer con Elasticsearch
        try:
            findings = get_findings(job_id, size=200, from_=0)
            module_runs = get_module_runs(job_id)
            if findings:
                reply['findings'] = findings
            if module_runs:
                reply['module_runs'] = module_runs
        except Exception:
            # Mejor esfuerzo: no fallar el API si ES no está disponible
            pass

        return reply
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving job: {str(e)}")
    finally:
        session.close()


@router.get("/jobs/{job_id}/findings")
def get_job_findings(job_id: str, size: int = 100, offset: int = 0, user=Depends(get_current_user)):
    """Return findings for a job from Elasticsearch (best-effort).
    Pagination via size/offset. Falls back to empty list if ES unavailable.
    """
    try:
        items = get_findings(job_id, size=size, from_=offset)
        return {"job_id": job_id, "findings": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying findings: {e}")


@router.get("/jobs/{job_id}/module_runs")
def get_job_module_runs(job_id: str, user=Depends(get_current_user)):
    """Return module_runs documents for a job from Elasticsearch (best-effort)."""
    try:
        items = get_module_runs(job_id)
        return {"job_id": job_id, "module_runs": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying module_runs: {e}")

@router.get("/jobs")
def list_jobs(
    user=Depends(get_current_user),
    limit: int = 20,
    offset: int = 0,
    status: str = None
):
    """
    Listar jobs con paginación y filtros
    """
    session = get_session()
    try:
        base_query = "SELECT job_id, status, input_type, input_value, created_at FROM jobs WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM jobs WHERE 1=1"
        params = {}
        
        if status:
            base_query += " AND status = :status"
            count_query += " AND status = :status"
            params["status"] = status
        
        base_query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset
        
        # Obtener jobs
        jobs_result = session.execute(text(base_query), params).fetchall()
        
        # Obtener total count
        total_count = session.execute(text(count_query), params).fetchone()[0]
        
        jobs = []
        for row in jobs_result:
            jobs.append({
                "job_id": row[0],
                "status": row[1],
                "input_type": row[2],
                "input_value": row[3],
                "created_at": row[4].isoformat() if row[4] else None
            })
        
        return {
            "jobs": jobs,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + len(jobs)) < total_count
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing jobs: {str(e)}")
    finally:
        session.close()

@router.get("/health")
def health_check():
    """
    Health check del servicio
    """
    return {
        "status": "healthy", 
        "service": "OSINT API",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/test-db")
def test_db_connection():
    """
    Endpoint para probar conexión a la base de datos
    """
    try:
        session = get_session()
        # Probar conexión y schema
        result = session.execute(text("""
            SELECT COUNT(*) as job_count, 
                   COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count
            FROM jobs
        """)).fetchone()
        session.close()
        
        return {
            "database": "connected", 
            "status": "healthy",
            "metrics": {
                "total_jobs": result[0],
                "completed_jobs": result[1]
            }
        }
    except Exception as e:
        return {
            "database": "error", 
            "status": "unhealthy", 
            "error": str(e)
        }

# Nuevo endpoint para estadísticas (útil para futuro)
@router.get("/stats")
def get_stats(user=Depends(get_current_user)):
    """
    Estadísticas del sistema
    """
    session = get_session()
    try:
        stats_query = text("""
            SELECT 
                COUNT(*) as total_jobs,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_jobs,
                COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing_jobs,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_jobs,
                AVG(CASE WHEN result IS NOT NULL THEN 1 ELSE 0 END) as success_rate
            FROM jobs
        """)
        
        result = session.execute(stats_query).fetchone()
        
        return {
            "stats": {
                "total_jobs": result[0],
                "completed_jobs": result[1],
                "processing_jobs": result[2],
                "failed_jobs": result[3],
                "success_rate": float(result[4]) if result[4] else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")
    finally:
        session.close()

