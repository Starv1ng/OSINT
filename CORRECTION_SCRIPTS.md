# SCRIPTS DE CORRECCIÓN

## 1. LIMPIAR BACKUP DUPLICADO

```bash
#!/bin/bash
# Script para archivar/eliminar backup

# Opción A: Archivar (más seguro)
tar -czf BACKUP_v1_20260119_030919.tar.gz BACKUP_v1_20260119_030919/
rm -rf BACKUP_v1_20260119_030919/

# Opción B: Eliminar directamente (si confías)
rm -rf BACKUP_v1_20260119_030919/

# Verificar
ls -la | grep BACKUP
# No debería mostrar nada
```

## 2. REMOVER CÓDIGO MUERTO

### A. En coordinator.py - Eliminar ModuleOrchestrator

**Cambio:**
```diff
# Línea 11
- from .orchestrator import ModuleOrchestrator
  from .dynamic_orchestrator import DynamicModuleOrchestrator

# Línea 52-53
- module_orchestrator = ModuleOrchestrator()
- dynamic_orchestrator = DynamicModuleOrchestrator(...)

+ dynamic_orchestrator = DynamicModuleOrchestrator(...)
```

### B. En coordinator.py - Eliminar funciones muertas

**Cambio:**
```diff
# Línea 159-173
- def process_osint_job_dynamic(self, job_id: str, search_data: dict):
-     """Procesamiento dinámico con orquestador dinámico"""
-     ...
-
- def process_osint_job_static(self, job_id: str, search_data: dict):
-     """Procesamiento estático con módulos predefinidos"""
-     ...

# Mantener SOLO:
+ @app.task(bind=True, name='process_osint_job')
+ def process_osint_job(self, job_id: str, search_data: dict):
+     ...
```

### C. Eliminar o integrar routes.py

**Opción 1: Eliminar (si routes_v2 cubre todo)**
```bash
rm services/api/app/api/routes.py
```

**Opción 2: Integrar versiones**
```bash
# Renombrar
mv services/api/app/api/routes.py services/api/app/api/routes_v1.py

# Editar main.py
cat > services/api/app/main.py << 'EOF'
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
from api.routes_v1 import router as api_router_v1
from api.routes_v2 import router as api_router_v2
from templates import templates

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="OSINT API Gateway v2.0")

# Middleware setup...
@app.middleware("http")
async def no_cache_js(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.endswith((".js", ".css", ".html")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Registrar versiones
app.include_router(api_router_v1, prefix="/api/v1")
app.include_router(api_router_v2, prefix="/api/v2")

# Endpoints estáticos...
EOF
```

## 3. CONSOLIDAR RUTAS DUPLICADAS

### A. `/jobs/{job_id}/module-runs` - Mantener versión ES

**En routes_v2.py:**
```python
# ELIMINAR: Primera definición (línea ~358)
# @router.get("/jobs/{job_id}/module-runs")
# def get_module_runs(job_id: str, user=Depends(get_current_user)):
#     runs = pg_client.get_module_runs(job_id)
#     return {"job_id": job_id, "module_runs": runs}

# MANTENER: Segunda definición (línea ~743) como ÚNICA
@router.get("/jobs/{job_id}/module-runs")
def get_module_runs(
    job_id: str,
    user=Depends(get_current_user),
    limit: int = Query(default=100, le=settings.API_MAX_LIMIT)
):
    try:
        result = es_client.get_module_runs(job_id, limit)
        return {
            "job_id": job_id,
            "module_runs": result.get('hits', []),
            "total": result.get('total', 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### B. `/jobs/{job_id}/findings/by-module` - Consolidar

**Solución:**
```python
@router.get("/jobs/{job_id}/findings/by-module")
def get_findings_by_module(
    job_id: str,
    user=Depends(get_current_user),
    limit: int = Query(default=100, le=settings.API_MAX_LIMIT)
):
    """Get findings grouped by module."""
    try:
        aggs = es_client.get_aggregations(job_id, ["module_name"])
        
        # Handle both response formats for compatibility
        if isinstance(aggs, dict):
            if "module_name_counts" in aggs:
                buckets = aggs.get("module_name_counts", [])
            else:
                buckets = aggs.get("buckets", [])
        else:
            buckets = []
        
        results = [
            {"module": bucket.get("key"), "count": bucket.get("doc_count", 0)}
            for bucket in buckets
        ]
        
        return {
            "job_id": job_id,
            "modules": results,
            "total_modules": len(results),
            "total_findings": sum(r["count"] for r in results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### C. `/jobs/{job_id}/findings/by-confidence` - Consolidar con formato

```python
@router.get("/jobs/{job_id}/findings/by-confidence")
def get_findings_by_confidence(
    job_id: str,
    user=Depends(get_current_user),
    format: str = Query("ranges", regex="ranges|categories")
):
    """
    Get findings grouped by confidence level.
    
    Params:
    - format: 'ranges' for percentage buckets (0-20%, 20-40%, etc.)
              'categories' for easy/medium/high/very_high
    """
    try:
        if format == "ranges":
            # Efficient: use ES aggregation
            body = {
                "size": 0,
                "query": {"term": {"job_id": job_id}},
                "aggs": {
                    "confidence_ranges": {
                        "range": {
                            "field": "confidence",
                            "ranges": [
                                {"to": 0.2},
                                {"from": 0.2, "to": 0.4},
                                {"from": 0.4, "to": 0.6},
                                {"from": 0.6, "to": 0.8},
                                {"from": 0.8, "to": 1.01}
                            ]
                        }
                    }
                }
            }
            result = es_client.es.search(index=es_client.findings_index, body=body)
            buckets = result.get("aggregations", {}).get("confidence_ranges", {}).get("buckets", [])
            
            labels = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]
            formatted = [
                {
                    "label": labels[idx] if idx < len(labels) else bucket.get("key", ""),
                    "count": bucket.get("doc_count", 0)
                }
                for idx, bucket in enumerate(buckets)
            ]
            return {"job_id": job_id, "format": "ranges", "buckets": formatted}
        
        else:  # categories
            findings = es_client.search_findings(filters={"job_id": job_id}, size=10000)
            categories = {"very_high": 0, "high": 0, "medium": 0, "low": 0}
            
            for finding in findings['hits']:
                conf = finding.get('confidence', 0)
                if conf >= 0.8:
                    categories["very_high"] += 1
                elif conf >= 0.6:
                    categories["high"] += 1
                elif conf >= 0.4:
                    categories["medium"] += 1
                else:
                    categories["low"] += 1
            
            return {"job_id": job_id, "format": "categories", "distribution": categories}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## 4. IMPLEMENTAR get_system_stats CORRECTAMENTE

```python
@router.get("/stats")
def get_system_stats(user=Depends(get_current_user)):
    """Get system-wide statistics."""
    try:
        # Query real data, not hardcoded
        findings_result = es_client.search_findings(filters={}, size=1)
        total_findings = findings_result.get('total', 0) if findings_result else 0
        
        total_indicators = pg_client.count_indicators() or 0
        total_jobs = pg_client.count_jobs() or 0
        
        # Get Neo4j stats if available
        try:
            neo4j_stats = neo4j_client.get_statistics()
        except:
            neo4j_stats = {}
        
        return {
            "total_findings": total_findings,
            "total_indicators": total_indicators,
            "total_jobs": total_jobs,
            "neo4j_stats": neo4j_stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

## 5. IMPLEMENTAR get_batch_results CORRECTAMENTE

```python
@router.get("/batch/{batch_id}/results")
def get_batch_results(batch_id: str, user=Depends(get_current_user)):
    """Get results for a batch of jobs."""
    try:
        # Query batch from database
        batch = pg_client.get_batch(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # Get all jobs in batch
        batch_jobs = pg_client.get_batch_jobs(batch_id)
        
        if not batch_jobs:
            return {
                "batch_id": batch_id,
                "jobs": [],
                "completed": 0,
                "failed": 0,
                "processing": 0,
                "status": "empty"
            }
        
        # Count statuses
        completed = sum(1 for j in batch_jobs if j.get('status') == 'completed')
        failed = sum(1 for j in batch_jobs if j.get('status') == 'failed')
        processing = sum(1 for j in batch_jobs if j.get('status') in ['accepted', 'processing'])
        
        return {
            "batch_id": batch_id,
            "jobs": batch_jobs,
            "completed": completed,
            "failed": failed,
            "processing": processing,
            "total": len(batch_jobs),
            "success_rate": completed / len(batch_jobs) if batch_jobs else 0
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch results: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

## 6. MEJORAR MANEJO DE ERRORES EN create_job

```python
@router.post("/jobs", status_code=202)
def create_job(req: IngestRequest, user=Depends(get_current_user)):
    """Create and enqueue a new OSINT job."""
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    
    try:
        # Step 1: Save to database
        try:
            pg_client.create_job(job_id, req.requester_id, req.input_type, req.value)
        except Exception as e:
            logger.error(f"Failed to create job in database: {e}")
            raise HTTPException(status_code=500, detail="Database error")
        
        # Step 2: Prepare enqueue data
        enqueue_data = req.dict()
        enqueue_data['max_iterations'] = req.max_iterations or settings.MAX_ITERATIONS
        enqueue_data['relevance_threshold'] = req.relevance_threshold or settings.RELEVANCE_THRESHOLD
        enqueue_data['execution_mode'] = req.execution_mode or settings.EXECUTION_MODE
        
        # Step 3: Enqueue job
        try:
            enqueue_result = enqueue_job(job_id, enqueue_data)
        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id}: {e}")
            # Mark as failed
            pg_client.update_job_status(job_id, "failed", error=f"Enqueue failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to enqueue job")
        
        # Success
        logger.info(f"Created job {job_id}, task_id: {enqueue_result.get('task_id')}")
        return {
            "job_id": job_id,
            "status": "accepted",
            "task_id": enqueue_result.get("task_id"),
            "config": {
                "max_iterations": enqueue_data['max_iterations'],
                "relevance_threshold": enqueue_data['relevance_threshold'],
                "execution_mode": enqueue_data['execution_mode']
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

## 7. MEJORAR RETRY CON BACKOFF

```python
@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, user=Depends(get_current_user)):
    """Retry a failed job with exponential backoff."""
    MAX_RETRIES = 3
    
    try:
        # Get job status
        job_stats = pg_client.get_job_statistics(job_id)
        if not job_stats:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job_stats.get("status") == "completed":
            raise HTTPException(status_code=400, detail="Job already completed")
        
        # Check retry count
        retry_count = job_stats.get("retry_count", 0)
        if retry_count >= MAX_RETRIES:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum retries ({MAX_RETRIES}) exceeded"
            )
        
        # Increment retry count
        pg_client.increment_retry_count(job_id)
        
        # Calculate exponential backoff (5 min, 15 min, 45 min)
        delay = min(5 * (3 ** retry_count) * 60, 3600)  # Max 1 hour
        
        # Enqueue with delay
        original_data = pg_client.get_job_data(job_id)
        enqueue_result = enqueue_job(
            job_id,
            {**original_data, "retry": True, "retry_count": retry_count + 1},
            countdown=delay
        )
        
        # Log the retry
        pg_client.create_audit_log({
            "action": "job_retry",
            "resource_type": "job",
            "resource_id": job_id,
            "retry_count": retry_count + 1,
            "delay_seconds": delay,
            "initiated_by": user.get("username")
        })
        
        logger.info(f"Job {job_id} retried (attempt {retry_count + 1}/{MAX_RETRIES}, delay {delay}s)")
        
        return {
            "job_id": job_id,
            "status": "retrying",
            "retry_count": retry_count + 1,
            "max_retries": MAX_RETRIES,
            "delay_seconds": delay,
            "task_id": enqueue_result.get("task_id")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying job: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

## 8. VERIFICACIÓN POST-APLICACIÓN

```bash
#!/bin/bash

echo "=== Verificación de cambios aplicados ==="

# 1. Verificar que no hay rutas duplicadas
echo -e "\n1. Buscando rutas duplicadas..."
grep -n "@router.get\|@router.post" services/api/app/api/routes_v2.py | \
    awk -F: '{print $3}' | sort | uniq -c | awk '$1 > 1 {print "❌ RUTA DUPLICADA:", $3}' || echo "✅ Sin duplicados"

# 2. Verificar que no hay referencias a ModuleOrchestrator
echo -e "\n2. Verificando ModuleOrchestrator..."
grep -r "module_orchestrator\." services/worker/ 2>/dev/null && echo "❌ Aún se usa" || echo "✅ No se usa"

# 3. Verificar que functions muertas fueron eliminadas
echo -e "\n3. Verificando funciones muertas..."
grep -c "process_osint_job_static\|process_osint_job_dynamic" services/worker/tasks/coordinator.py 2>/dev/null || echo "✅ Eliminadas"

# 4. Verificar que routes.py no se importa
echo -e "\n4. Verificando routes.py..."
grep "from api.routes import" services/api/app/*.py 2>/dev/null && echo "❌ Aún se importa" || echo "✅ No se importa"

# 5. Verificar que no hay código hardcodeado
echo -e "\n5. Buscando hardcoded values en stats..."
grep -A5 'get_system_stats' services/api/app/api/routes_v2.py | grep -E '"total_findings": 0|"total_jobs": 0' && echo "❌ Mock data aún presente" || echo "✅ Implementado realmente"

echo -e "\n✅ Verificación completada"
```

## ORDEN DE APLICACIÓN RECOMENDADO

1. **Ejecutar limpieza de backup**
2. **Aplicar cambios en coordinator.py** (remover código muerto)
3. **Consolidar rutas en routes_v2.py**
4. **Actualizar main.py** (registrar versiones correctamente)
5. **Implementar funciones reales** (batch, stats, etc.)
6. **Ejecutar verificación post-aplicación**
7. **Pruebas de regresión**

