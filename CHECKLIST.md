# ✅ CHECKLIST DE CORRECCIONES

## Fase 1: CRÍTICA - Limpiar Código Muerto (1-2 horas)

### 1.1 Eliminar Backup Completo
- [ ] Archivar `BACKUP_v1_20260119_030919.tar.gz`
```bash
cd /path/to/OSINT
tar -czf BACKUP_v1_20260119_030919.tar.gz BACKUP_v1_20260119_030919/
rm -rf BACKUP_v1_20260119_030919/
```
- [ ] Verificar eliminación
```bash
ls -la | grep BACKUP  # No debe mostrar nada
```
- [ ] Commit a git
```bash
git add -A
git commit -m "chore: remove old v1 backup"
```

### 1.2 Eliminar ModuleOrchestrator
**Archivo:** `services/worker/tasks/coordinator.py`

- [ ] Línea 11: Eliminar import
```python
# from .orchestrator import ModuleOrchestrator  # ELIMINAR
from .dynamic_orchestrator import DynamicModuleOrchestrator
```

- [ ] Línea 52: Eliminar instancia
```python
# module_orchestrator = ModuleOrchestrator()  # ELIMINAR
dynamic_orchestrator = DynamicModuleOrchestrator(
    max_iterations=settings.MAX_ITERATIONS,
    relevance_threshold=settings.RELEVANCE_THRESHOLD,
    execution_mode=settings.EXECUTION_MODE
)
```

- [ ] Verificar no quedan referencias
```bash
grep -r "module_orchestrator" services/worker/
# Debe estar vacío
```

### 1.3 Eliminar Funciones Muertas
**Archivo:** `services/worker/tasks/coordinator.py`

- [ ] Eliminar `process_osint_job_dynamic()` (líneas ~159-165)
```python
# def process_osint_job_dynamic(self, job_id: str, search_data: dict):
#     """Procesamiento dinámico con orquestador dinámico"""
#     ...
# ELIMINAR COMPLETAMENTE
```

- [ ] Eliminar `process_osint_job_static()` (líneas ~167-173)
```python
# def process_osint_job_static(self, job_id: str, search_data: dict):
#     """Procesamiento estático con módulos predefinidos"""
#     ...
# ELIMINAR COMPLETAMENTE
```

- [ ] Verificar que solo queda `process_osint_job`
```bash
grep "def process_osint_job" services/worker/tasks/coordinator.py
# Debe mostrar solo una definición (sin _dynamic o _static)
```

### 1.4 Eliminar o Integrar routes.py
**Archivo:** `services/api/app/api/routes.py`

**Opción A: Eliminar (Recomendado si routes_v2 cubre todo)**
- [ ] Verificar que routes_v2.py tiene todos los endpoints
```bash
grep "@router" services/api/app/api/routes.py | wc -l       # Contar endpoints
grep "@router" services/api/app/api/routes_v2.py | wc -l    # Comparar
```

- [ ] Eliminar archivo
```bash
rm services/api/app/api/routes.py
```

- [ ] Verificar no quedan imports
```bash
grep "from api.routes import\|from api.routes_v1 import" services/api/
# Debe estar vacío
```

**Opción B: Integrar (Si hay diferencias entre v1 y v2)**
- [ ] Renombrar
```bash
mv services/api/app/api/routes.py services/api/app/api/routes_v1.py
```

- [ ] Actualizar main.py (ver sección 2.1)

---

## Fase 2: CONSISTENCIA - Consolidar Rutas (1-2 horas)

### 2.1 Arreglar Importación de Rutas en main.py
**Archivo:** `services/api/app/main.py`

**Si decidiste eliminar routes.py:**
```python
# Sin cambios, ya usa solo routes_v2
```

**Si decidiste integrar routes_v1 y routes_v2:**
- [ ] Actualizar imports
```python
from api.routes_v1 import router as api_router_v1
from api.routes_v2 import router as api_router_v2
```

- [ ] Registrar ambas
```python
app.include_router(api_router_v1, prefix="/api/v1")
app.include_router(api_router_v2, prefix="/api/v2")
```

### 2.2 Consolidar `/jobs/{job_id}/module-runs`
**Archivo:** `services/api/app/api/routes_v2.py`

- [ ] Localizar primera definición (línea ~358)
```python
@router.get("/jobs/{job_id}/module-runs")
def get_module_runs(job_id: str, user=Depends(get_current_user)):
    """Return recorded module runs for a given job."""
```

- [ ] Eliminar completamente (es redundante)

- [ ] Verificar segunda definición existe (línea ~743)
```python
@router.get("/jobs/{job_id}/module-runs")
def get_module_runs(
    job_id: str,
    user=Depends(get_current_user),
    limit: int = Query(default=100, le=settings.API_MAX_LIMIT)
):
```

- [ ] Renombrar a `get_job_module_runs` para evitar warnings
```python
def get_job_module_runs(  # Cambiar nombre
    job_id: str,
    user=Depends(get_current_user),
    limit: int = Query(default=100, le=settings.API_MAX_LIMIT)
):
```

### 2.3 Consolidar `/jobs/{job_id}/findings/by-module`
**Archivo:** `services/api/app/api/routes_v2.py`

- [ ] Combinar ambas definiciones en UNA función
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
            "modules": results,
            "total_modules": len(results),
            "total_findings": sum(r["count"] for r in results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] Eliminar la otra definición (mantener solo una)

### 2.4 Consolidar `/jobs/{job_id}/findings/by-confidence`
**Archivo:** `services/api/app/api/routes_v2.py`

- [ ] Combinar en UNA función con parámetro `format`
```python
@router.get("/jobs/{job_id}/findings/by-confidence")
def get_findings_by_confidence(
    job_id: str,
    user=Depends(get_current_user),
    format: str = Query("ranges", regex="ranges|categories")
):
    """Get findings grouped by confidence (see TECHNICAL_ANALYSIS.md)"""
    # ... implementación completa en TECHNICAL_ANALYSIS.md
```

- [ ] Verificar que maneja ambos formatos correctamente

---

## Fase 3: FUNCIONALIDAD - Implementar Realmente (2-3 horas)

### 3.1 Implementar get_system_stats Realmente
**Archivo:** `services/api/app/api/routes_v2.py`

- [ ] Localizar `@router.get("/stats")`

- [ ] Reemplazar mock data con queries reales (ver TECHNICAL_ANALYSIS.md)

- [ ] Verificar que consulta:
  - [ ] PostgreSQL para total_jobs
  - [ ] PostgreSQL para total_indicators
  - [ ] Elasticsearch para total_findings
  - [ ] Neo4j para neo4j_stats

- [ ] Test manualmente
```bash
curl http://localhost:8000/api/v2/stats
# Debe retornar números reales, no ceros
```

### 3.2 Implementar get_batch_results Realmente
**Archivo:** `services/api/app/api/routes_v2.py`

- [ ] Localizar `@router.get("/batch/{batch_id}/results")`

- [ ] Reemplazar mock data con:
  - [ ] `pg_client.get_batch(batch_id)`
  - [ ] `pg_client.get_batch_jobs(batch_id)`
  - [ ] Contador de estados (completed, failed, processing)

- [ ] Nota: Requiere tabla `batches` en PostgreSQL
  ```sql
  -- Si no existe, crear:
  CREATE TABLE IF NOT EXISTS batches (
      batch_id VARCHAR(50) PRIMARY KEY,
      created_at TIMESTAMP DEFAULT NOW(),
      created_by VARCHAR(255),
      status VARCHAR(20) DEFAULT 'processing'
  );
  
  CREATE TABLE IF NOT EXISTS batch_jobs (
      id SERIAL PRIMARY KEY,
      batch_id VARCHAR(50) REFERENCES batches(batch_id),
      job_id VARCHAR(50) UNIQUE,
      status VARCHAR(20)
  );
  ```

### 3.3 Mejorar create_job Transacción
**Archivo:** `services/api/app/api/routes_v2.py`

- [ ] Localizar `@router.post("/jobs")`

- [ ] Implementar cleanup en error (ver TECHNICAL_ANALYSIS.md)
  - [ ] Si enqueue falla, marcar job como "failed"
  - [ ] Loguear el error real

- [ ] Test con Celery desconectado
```bash
# Desconectar Redis
docker stop redis
curl -X POST http://localhost:8000/api/v2/jobs \
  -H "Content-Type: application/json" \
  -d '{"value": "test@example.com"}'
# Debe retornar error 500, job debe estar marcado como failed
```

### 3.4 Mejorar retry_job con Backoff
**Archivo:** `services/api/app/api/routes_v2.py`

- [ ] Localizar `@router.post("/jobs/{job_id}/retry")`

- [ ] Implementar (ver TECHNICAL_ANALYSIS.md):
  - [ ] Contador de reintentos
  - [ ] Límite máximo (MAX_RETRIES = 3)
  - [ ] Backoff exponencial (5min, 15min, 45min)
  - [ ] Audit log

- [ ] Test de reintentos
```bash
curl -X POST http://localhost:8000/api/v2/jobs/test-job/retry
# Respuesta 1: retry_count=1, delay_seconds=300
curl -X POST http://localhost:8000/api/v2/jobs/test-job/retry
# Respuesta 2: retry_count=2, delay_seconds=900
curl -X POST http://localhost:8000/api/v2/jobs/test-job/retry
# Respuesta 3: retry_count=3, delay_seconds=2700
curl -X POST http://localhost:8000/api/v2/jobs/test-job/retry
# Respuesta 4: Error 400 "Maximum retries (3) exceeded"
```

---

## Fase 4: VERIFICACIÓN - Testing (1 hora)

### 4.1 Pruebas de Rutas Duplicadas
- [ ] Verificar que no hay warnings de ruta duplicada en startup
```bash
docker logs osint_api | grep -i "duplicate\|warning"
# Debe estar vacío
```

- [ ] Test cada ruta consolidada
```bash
curl http://localhost:8000/api/v2/jobs/test-job/module-runs?limit=10
curl http://localhost:8000/api/v2/jobs/test-job/findings/by-module
curl http://localhost:8000/api/v2/jobs/test-job/findings/by-confidence?format=ranges
curl http://localhost:8000/api/v2/jobs/test-job/findings/by-confidence?format=categories
```

### 4.2 Pruebas de Datos Reales
- [ ] Verificar get_system_stats
```bash
curl http://localhost:8000/api/v2/stats
# Debe retornar números > 0 si hay datos
```

- [ ] Verificar get_batch_results
```bash
curl http://localhost:8000/api/v2/batch/test-batch/results
# Debe retornar datos reales o 404
```

### 4.3 Pruebas de Transacciones
- [ ] Test create_job con éxito
```bash
curl -X POST http://localhost:8000/api/v2/jobs \
  -H "Content-Type: application/json" \
  -d '{"value": "test@example.com", "input_type": "email"}'
# Status 202, job_id válido
```

- [ ] Verificar job fue guardado en BD
```bash
curl http://localhost:8000/api/v2/jobs/{job_id_del_paso_anterior}
# Status 200, datos correctos
```

### 4.4 Pruebas de Retry
- [ ] Test retry con contador
```bash
# Crear job que vaya a fallar
# Ejecutar 3 retries
# Verificar que en 4to retry falla con "Max retries exceeded"
```

---

## Fase 5: FINALIZACIÓN - Limpieza y Documentación (30 min)

### 5.1 Git Commits
- [ ] Commit Fase 1
```bash
git add -A
git commit -m "fix: remove dead code and backup v1

- Remove BACKUP_v1_20260119_030919/
- Remove ModuleOrchestrator
- Remove process_osint_job_static/dynamic
- Remove unused routes.py

Fixes #XXX"
```

- [ ] Commit Fase 2
```bash
git add -A
git commit -m "refactor: consolidate duplicate API routes

- Consolidate GET /jobs/{job_id}/module-runs
- Consolidate GET /jobs/{job_id}/findings/by-module
- Consolidate GET /jobs/{job_id}/findings/by-confidence

Fixes #XXX"
```

- [ ] Commit Fase 3
```bash
git add -A
git commit -m "feat: implement real data retrieval and fix transactions

- Implement get_system_stats with real queries
- Implement get_batch_results with database
- Improve create_job transaction handling
- Add exponential backoff to retry_job
- Add audit logging

Fixes #XXX"
```

### 5.2 Documentación
- [ ] Actualizar README con cambios
- [ ] Actualizar CHANGELOG.md
- [ ] Crear PR con descripción de cambios

### 5.3 Verificación Final
- [ ] Ejecutar script de verificación
```bash
bash CORRECTION_SCRIPTS.md  # Sección 8
```

- [ ] Todos los tests pasan
- [ ] No hay warnings en logs
- [ ] Endpoints retornan datos reales

---

## 📋 Estado del Proyecto

**Antes de correcciones:**
```
✗ 270+ archivos duplicados
✗ 3 rutas API duplicadas
✗ 4+ funciones muertas
✗ 3+ endpoints con mock data
✗ Transacciones rotas
✗ Configuración redundante
```

**Después de correcciones:**
```
✓ Proyecto limpio (sin duplicados)
✓ Rutas API consolidadas y consistentes
✓ Código muerto eliminado
✓ Todos los endpoints retornan datos reales
✓ Transacciones con manejo de errores
✓ Configuración centralizada
```

---

## ❓ Preguntas & Respuestas

**P: ¿Cuánto tiempo toma completar todo?**  
R: ~6-8 horas de trabajo concentrado. Puede hacerse en 2 sprints (4 horas cada uno).

**P: ¿Necesito hacer backup antes?**  
R: Sí, especialmente la carpeta BACKUP_v1. Aunque está duplicada, archívala primero.

**P: ¿Qué pasa si algo falla durante la corrección?**  
R: Git es tu amigo. Cada fase es un commit. Si falla, hace revert simple.

**P: ¿Debo hacer tests antes de empezar?**  
R: No necesariamente, pero es recomendable tener un entorno de testing limpio.

**P: ¿Puedo hacer esto en paralelo?**  
R: Fase 1 es independiente. Fase 2 requiere Fase 1. Fases 3+ se pueden hacer juntas.

---

## 🚀 Siguiente Paso

Una vez completado todo:
1. Merge a `main` branch
2. Deploy a staging
3. Testing completo
4. Deploy a producción
5. Monitoreo de estabilidad

**Status:** ✅ Listo para ejecutar

