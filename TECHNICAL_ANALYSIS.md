# ANÁLISIS TÉCNICO DETALLADO - Incongruencias Encontradas

## 1. RUTAS API DUPLICADAS - ANÁLISIS LÍNEA POR LÍNEA

### 1.1 Duplicado: `/jobs/{job_id}/module-runs`

#### Primera definición (línea ~358)
```python
@router.get("/jobs/{job_id}/module-runs")
def get_module_runs(job_id: str, user=Depends(get_current_user)):
    """Return recorded module runs for a given job."""
    try:
        runs = pg_client.get_module_runs(job_id)
        return {"job_id": job_id, "module_runs": runs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Problemas:**
- Nombre: `get_module_runs`
- Accede a: `pg_client` (PostgreSQL)
- Retorna: `{"job_id": ..., "module_runs": runs}`
- Parámetros: Solo path params

#### Segunda definición (línea ~743)
```python
@router.get("/jobs/{job_id}/module-runs")
def get_job_module_runs(
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

**Problemas:**
- Nombre: `get_job_module_runs` (diferente, genera advertencia)
- Accede a: `es_client` (Elasticsearch)
- Retorna: Añade campo `total`
- Parámetros: Incluye `limit`

**¿Qué sucede en FastAPI?**
- FastAPI NO permite dos rutas idénticas
- La SEGUNDA definición sobrescribe la PRIMERA
- La primera nunca se ejecuta
- Al recargar el módulo, FastAPI advertirá sobre redefinición

**Prueba para verificar:**
```bash
curl http://localhost:8000/api/v2/jobs/test-job-123/module-runs
# Usará ES, NO PostgreSQL
```

**Solución:**
```python
# OPCIÓN A: Mantener versión ES (más completa)
@router.get("/jobs/{job_id}/module-runs")
def get_job_module_runs(
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

# ELIMINAR: Segunda definición (línea ~358)
```

---

### 1.2 Duplicado: `/jobs/{job_id}/findings/by-module`

#### Primera definición (línea ~177)
```python
@router.get("/jobs/{job_id}/findings/by-module")
def get_findings_by_module(job_id: str, user=Depends(get_current_user)):
    """Aggregate findings count grouped by module."""
    try:
        aggs = es_client.get_aggregations(job_id, ["module_name"])
        buckets = aggs.get("module_name_counts", []) if aggs else []
        results = [
            {"module": bucket.get("key"), "count": bucket.get("doc_count", 0)}
            for bucket in buckets
        ]
        return {"job_id": job_id, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### Segunda definición (línea ~700)
```python
@router.get("/jobs/{job_id}/findings/by-module")
def get_findings_by_module(
    job_id: str,
    user=Depends(get_current_user),
    limit: int = Query(default=100, le=settings.API_MAX_LIMIT)
):
    try:
        agg_result = es_client.get_aggregations(job_id, ["module_name"])
        return {
            "job_id": job_id,
            "findings_by_module": agg_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Diferencias:**
| Aspecto | Primera | Segunda |
|---------|---------|---------|
| Formato respuesta | `{"results": [...]}` | `{"findings_by_module": ...}` |
| Parseo | Manual (buckets) | Directo (agg_result) | 
| Parámetros | Sin limit | Con limit |
| Manejo ES | Espera `module_name_counts` | Espera directo en agg_result |

**Impacto:** Dependiendo de cómo `es_client.get_aggregations()` retorne datos:
- Si retorna `{module_name_counts: [...]}` → Primera sería correcta
- Si retorna `{...}` → Segunda será correcta

**Solución uniforme:**
```python
@router.get("/jobs/{job_id}/findings/by-module")
def get_findings_by_module(
    job_id: str,
    user=Depends(get_current_user),
    limit: int = Query(default=100, le=settings.API_MAX_LIMIT)
):
    """Aggregate findings grouped by module name."""
    try:
        aggs = es_client.get_aggregations(job_id, ["module_name"])
        
        # Handle both response formats
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
            "module_name": results,
            "total": sum(r["count"] for r in results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

### 1.3 Duplicado: `/jobs/{job_id}/findings/by-confidence`

#### Primera definición (línea ~200)
```python
@router.get("/jobs/{job_id}/findings/by-confidence")
def get_findings_by_confidence(job_id: str, user=Depends(get_current_user)):
    """Aggregate findings into confidence buckets for charts."""
    try:
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
        buckets = result.get("aggregations", {})\
            .get("confidence_ranges", {})\
            .get("buckets", [])

        labels = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]
        formatted = []
        for idx, bucket in enumerate(buckets):
            formatted.append({
                "label": labels[idx] if idx < len(labels) else bucket.get("key", ""),
                "count": bucket.get("doc_count", 0)
            })

        return {"job_id": job_id, "buckets": formatted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Características:**
- Usa consulta ES directa con agregación de rango
- Formato predefinido: 5 buckets (0-20%, 20-40%, etc.)
- Retorna: `{"job_id": ..., "buckets": [...]}`

#### Segunda definición (línea ~721)
```python
@router.get("/jobs/{job_id}/findings/by-confidence")
def get_findings_by_confidence(
    job_id: str,
    user=Depends(get_current_user),
    limit: int = Query(default=100, le=settings.API_MAX_LIMIT)
):
    try:
        findings = es_client.search_findings(filters={"job_id": job_id}, size=limit)
        
        confidence_buckets = {
            "very_high": [],
            "high": [],
            "medium": [],
            "low": []
        }
        
        for finding in findings['hits']:
            conf = finding.get('confidence', 0)
            if conf >= 0.8:
                confidence_buckets["very_high"].append(finding)
            elif conf >= 0.6:
                confidence_buckets["high"].append(finding)
            elif conf >= 0.4:
                confidence_buckets["medium"].append(finding)
            else:
                confidence_buckets["low"].append(finding)
        
        return {
            "job_id": job_id,
            "confidence_distribution": {k: len(v) for k, v in confidence_buckets.items()},
            "buckets": confidence_buckets
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Características:**
- Obtiene findings, procesamiento en Python
- Categorías: very_high (0.8-1), high (0.6-0.8), medium (0.4-0.6), low (<0.4)
- Retorna: `{"job_id": ..., "confidence_distribution": {...}, "buckets": {...}}`

**Problemas de compatibilidad:**
1. **Formatos diferentes:** Primera vs Segunda tienen estructura completamente diferente
2. **Performance:** Primera es más eficiente (agregación en ES), Segunda trae todos los findings
3. **Límites:** Primera sin límite, Segunda limitada a `limit` parámetro
4. **Exactitud:** Primera usa ES aggregation, Segunda procesa en memoria

**Cliente consumidor verá:**
```python
# Si recibe respuesta de Primera:
{"job_id": "x", "buckets": [{"label": "0-20%", "count": 5}, ...]}

# Si recibe respuesta de Segunda:
{"job_id": "x", "confidence_distribution": {"very_high": 10}, "buckets": {"very_high": [...], ...}}
```

**¡Incompatible!** El frontend romperá.

**Solución unificada (mantener Primera como más eficiente):**
```python
@router.get("/jobs/{job_id}/findings/by-confidence")
def get_findings_by_confidence(
    job_id: str,
    user=Depends(get_current_user),
    format: str = Query("ranges", regex="ranges|categories")
):
    """
    Get findings grouped by confidence.
    
    Params:
    - format: "ranges" para buckets porcentuales (0-20%, etc.)
              "categories" para easy/med/high/very_high
    """
    try:
        if format == "ranges":
            # Usar agregación ES (eficiente)
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

---

## 2. FUNCIONES MUERTAS - MAPEO DE LLAMADAS

### 2.1 `ModuleOrchestrator` - Nunca utilizado

**Instanciación:** `services/worker/tasks/coordinator.py` línea 52
```python
module_orchestrator = ModuleOrchestrator()  # ❌ NUNCA SE USA
```

**Búsqueda de referencias:**
```bash
grep -r "module_orchestrator\." services/
# RESULTADO: 0 matches

grep -r "ModuleOrchestrator" services/ --exclude-dir=.git
# RESULTADO: Solo en instantiation, imports, and backup
```

**¿Por qué existe?**
- Probablemente versión anterior antes de `DynamicModuleOrchestrator`
- Código legado no limpiado

**Dónde se usa `DynamicModuleOrchestrator`:**
```python
# services/worker/tasks/coordinator.py línea 59
@app.task(bind=True, name='process_osint_job')
def process_osint_job(self, job_id: str, search_data: dict):
    # ...
    results = asyncio.run(dynamic_orchestrator.execute_dynamic_search(job_id, search_data_enhanced))
```

**Solución:**
```python
# services/worker/tasks/coordinator.py
# ELIMINAR línea 12:
# from .orchestrator import ModuleOrchestrator

# ELIMINAR línea 52:
# module_orchestrator = ModuleOrchestrator()
```

---

### 2.2 `process_osint_job_static` - No es task Celery

**Ubicación:** `services/worker/tasks/coordinator.py` línea 167-173
```python
def process_osint_job_static(self, job_id: str, search_data: dict):  # ❌ NO @app.task
    """Procesamiento estático con módulos predefinidos"""
    # ... 20+ líneas de implementación
```

**Problemas:**
1. No tiene decorador `@app.task`
2. Por lo tanto, no puede ser encolada en Celery
3. Nunca se llama desde el código

**Búsqueda de referencias:**
```bash
grep -r "process_osint_job_static" services/
# RESULTADO: 0 matches en directorios activos
# Solo en BACKUP_v1
```

**¿Por qué existe?**
- Probablemente estrategia alternativa abandonada
- Tenía código de investigación que decidieron no usar

**Estado actual:**
- ~50 líneas de código muerto
- Confunde a nuevos desarrolladores
- Aumenta complejidad del módulo

---

### 2.3 `process_osint_job_dynamic` - No es task Celery

**Ubicación:** `services/worker/tasks/coordinator.py` línea 159-165
```python
def process_osint_job_dynamic(self, job_id: str, search_data: dict):  # ❌ NO @app.task
    """Procesamiento dinámico con orquestador dinámico"""
    # ... implementación
```

**Mismo problema que `process_osint_job_static`**

**Posible intención:**
```python
# Probablemente era:
@app.task(bind=True, name='process_osint_job_dynamic')
def process_osint_job_dynamic(self, job_id: str, search_data: dict):
    # ...

@app.task(bind=True, name='process_osint_job_static')
def process_osint_job_static(self, job_id: str, search_data: dict):
    # ...
```

**Pero decidieron usar solo `process_osint_job` que elige dinámico automáticamente:**
```python
@app.task(bind=True, name='process_osint_job')
def process_osint_job(self, job_id: str, search_data: dict):
    # ... análisis
    results = asyncio.run(dynamic_orchestrator.execute_dynamic_search(...))
```

---

### 2.4 `routes.py` - Archivo completo sin usar

**Ubicación:** `services/api/app/api/routes.py` (~262 líneas)

**¿Está registrado?** NO.

**En `main.py`:**
```python
from api.routes_v2 import router as api_router  # ❌ Solo routes_v2

app.include_router(api_router, prefix="/api/v2")
app.include_router(api_router, prefix="/api/v1")  # ❌ Ambas usan routes_v2
```

**Contenido de `routes.py`:**
- `@router.post("/ingest/name")` - endpoint de ingesta
- `@router.get("/jobs/{job_id}")` - obtener job
- `@router.get("/jobs")` - listar jobs
- Endpoints relacionados...

**¿Por qué no se usa?**
- Probablemente versión OLD que fue reemplazada por `routes_v2`
- No fue eliminada como "backup"
- Causa confusión de mantenimiento

**Impacto:**
```
- Si alguien modifica routes.py, cambios nunca tienen efecto
- Aumenta la carga cognitiva
- Es una "trampa" para nuevos desarrolladores
```

**Solución:**
```python
# OPCIÓN A: Eliminar completamente (si está cubierto por routes_v2)
rm services/api/app/api/routes.py

# OPCIÓN B: Renombrar a routes_v1 e integrar ambas
mv routes.py routes_v1.py
# Editar main.py:
from api.routes_v1 import router as api_router_v1
from api.routes_v2 import router as api_router_v2

app.include_router(api_router_v1, prefix="/api/v1")
app.include_router(api_router_v2, prefix="/api/v2")
```

---

## 3. CONFIGURACIÓN REDUNDANTE

### 3.1 Lectura múltiple de variables de entorno

**Patrón problemático:**

```python
# services/api/app/api/config.py
class Settings:
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "5"))
    RELEVANCE_THRESHOLD: float = float(os.getenv("RELEVANCE_THRESHOLD", "0.5"))
    EXECUTION_MODE: str = os.getenv("EXECUTION_MODE", "normal")

settings = Settings()
```

**LUEGO, en services/worker/tasks/coordinator.py:**
```python
dynamic_orchestrator = DynamicModuleOrchestrator(
    max_iterations=int(os.environ.get("MAX_ITERATIONS", "5")),  # ❌ DUPLICADO
    relevance_threshold=float(os.environ.get("RELEVANCE_THRESHOLD", "0.5")),  # ❌ DUPLICADO
    execution_mode=os.environ.get("EXECUTION_MODE", "normal")  # ❌ DUPLICADO
)
```

**Problemas:**
1. Si cambias en `config.py`, el worker sigue usando valores antiguos
2. Hay dos fuentes de verdad
3. Defaults pueden estar desincronizados
4. Mantenimiento más difícil

**Solución:**

```python
# services/worker/tasks/coordinator.py
from shared.config import settings  # O desde donde sea centralizado

dynamic_orchestrator = DynamicModuleOrchestrator(
    max_iterations=settings.MAX_ITERATIONS,
    relevance_threshold=settings.RELEVANCE_THRESHOLD,
    execution_mode=settings.EXECUTION_MODE
)
```

---

## 4. FLUJOS TRANSACCIONALES ROTOS

### 4.1 Race Condition en `create_job`

**Escenario problemático:**

```python
@router.post("/jobs", status_code=202)
def create_job(req: IngestRequest, user=Depends(get_current_user)):
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    
    try:
        # T1: Guardar en DB
        pg_client.create_job(job_id, req.requester_id, req.input_type, req.value)  # ✅ OK
        
        # T2: Encolar trabajo
        enqueue_result = enqueue_job(job_id, enqueue_data)  # ❌ Si FALLA aquí...
        
        return {...}
    except Exception as e:
        # Job ya está en DB pero nunca será procesado
        logger.error(...)
        raise
```

**Estados posibles:**

| Paso | Resultado | Estado Job |
|------|-----------|-----------|
| T1 success, T2 success | ✅ OK | Processing |
| T1 success, T2 fails | ❌ PROBLEMA | In DB but orphaned |
| T1 fails | ✅ OK | Not created |

**El problema:** Job huérfano - está en BD pero nunca se procesará.

**Cliente verá:**
```bash
GET /api/v2/jobs/job-abc123
# Retorna: status=accepted, but never transitions to processing

# Espera eternamente...
```

**Solución 1 - Cleanup en error:**
```python
@router.post("/jobs", status_code=202)
def create_job(req: IngestRequest, user=Depends(get_current_user)):
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    
    try:
        pg_client.create_job(job_id, req.requester_id, req.input_type, req.value)
        enqueue_data = req.dict()
        enqueue_data['max_iterations'] = req.max_iterations or settings.MAX_ITERATIONS
        enqueue_data['relevance_threshold'] = req.relevance_threshold or settings.RELEVANCE_THRESHOLD
        enqueue_data['execution_mode'] = req.execution_mode or settings.EXECUTION_MODE
        
        try:
            enqueue_result = enqueue_job(job_id, enqueue_data)
        except Exception as e:
            # Rollback: marcar como failed
            pg_client.update_job_status(job_id, "failed", error=str(e))
            logger.error(f"Failed to enqueue job {job_id}: {e}")
            raise
        
        return {
            "job_id": job_id,
            "status": "accepted",
            "task_id": enqueue_result.get("task_id")
        }
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Solución 2 - Usar Saga Pattern:**
```python
# Guardar job con status "enqueue_pending"
# Si enqueue falla, background job limpia orphans después de timeout
```

---

## 5. LÓGICA DE RETRY FRÁGIL

**Ubicación:** `routes_v2.py` línea 121

```python
@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, user=Depends(get_current_user)):
    try:
        enqueue_result = enqueue_job(job_id, {"retry": True})  # ❌ Problemas:
        return {
            "job_id": job_id,
            "status": "retrying",
            "task_id": enqueue_result.get("task_id")
        }
```

**Problemas:**

1. **Sin contador de reintentos:**
   ```python
   # Si llamamos 1000 veces a retry...
   for i in range(1000):
       retry_job("job-abc")  # ¡Se enqueuea 1000 veces!
   ```

2. **Sin backoff exponencial:**
   ```python
   # Retry immediato = carga en workers sin descanso
   ```

3. **Sin límite de reintentos:**
   ```python
   # Job puede quedar en retry infinito si hay error permanente
   ```

4. **Sin logging de intentos:**
   ```python
   # ¿Cuántas veces fue reintentado? Imposible saber.
   ```

**Solución robusta:**

```python
@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, user=Depends(get_current_user)):
    try:
        # 1. Obtener historial de job
        job_stats = pg_client.get_job_statistics(job_id)
        if not job_stats:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # 2. Verificar contador de reintentos
        retry_count = job_stats.get("retry_count", 0)
        MAX_RETRIES = 3
        
        if retry_count >= MAX_RETRIES:
            raise HTTPException(
                status_code=400, 
                detail=f"Max retries ({MAX_RETRIES}) exceeded"
            )
        
        # 3. Incrementar contador
        pg_client.increment_retry_count(job_id)
        
        # 4. Calcular backoff exponencial
        delay = min(2 ** retry_count * 60, 3600)  # Max 1 hora
        
        # 5. Encolar con delay
        enqueue_result = enqueue_job(
            job_id, 
            {"retry": True, "retry_count": retry_count + 1},
            countdown=delay
        )
        
        # 6. Loguear
        pg_client.create_audit_log({
            "action": "job_retry",
            "resource_id": job_id,
            "retry_count": retry_count + 1,
            "delay_seconds": delay,
            "initiated_by": user.get("username")
        })
        
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

---

## RESUMEN DE INCONGRUENCIAS

| # | Tipo | Ubicación | Severidad | Fácil Fix |
|----|------|-----------|-----------|-----------|
| 1 | Ruta duplicada | routes_v2.py:358, 743 | 🔴 Crítica | ✅ Sí |
| 2 | Ruta duplicada | routes_v2.py:177, 700 | 🔴 Crítica | ✅ Sí |
| 3 | Ruta duplicada | routes_v2.py:200, 721 | 🔴 Crítica | ⚠️ Medio |
| 4 | Código muerto | coordinator.py:52 | 🔴 Crítica | ✅ Sí |
| 5 | Código muerto | coordinator.py:159-165 | 🟡 Moderada | ✅ Sí |
| 6 | Código muerto | coordinator.py:167-173 | 🟡 Moderada | ✅ Sí |
| 7 | Archivo muerto | routes.py | 🔴 Crítica | ✅ Sí |
| 8 | Config redundante | coordinator.py:20-26 | 🟡 Moderada | ✅ Sí |
| 9 | Race condition | routes_v2.py:41 | 🔴 Crítica | ⚠️ Medio |
| 10 | Retry frágil | routes_v2.py:121 | 🟡 Moderada | ⚠️ Medio |
| 11 | Mock data | routes_v2.py:610, 673 | 🔴 Crítica | ⚠️ Medio |
| 12 | Batch sin persistencia | routes_v2.py:617 | 🔴 Crítica | ⚠️ Largo |

