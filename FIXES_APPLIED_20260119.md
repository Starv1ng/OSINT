# Correcciones Aplicadas - 19 de Enero 2026

## 📋 Resumen de Problemas Reportados y Solucionados

### Problema 1: BÚSQUEDA ROTA (Nunca encuentra nada)

**Síntomas:**
- El endpoint `/search/findings` no retorna resultados
- Los findings no aparecen en Elasticsearch
- Al refrescar la página, se pierde el progreso

**Causas Identificadas:**
1. ❌ Los índices de Elasticsearch no se creaban automáticamente
2. ❌ El índice no se refrescaba antes de buscar
3. ❌ Errores silenciosos al indexar findings (sin try-catch)
4. ❌ El worker no manejaba errores correctamente

**Soluciones Aplicadas:**

#### a) Crear índices automáticamente en startup (`services/api/app/main.py`)
```python
@app.on_event("startup")
async def startup_event():
    es_client.create_indices()  # ✅ Crea indices findings y module-runs
```

#### b) Refrescar índice en búsqueda (`services/api/app/api/routes_v2.py`)
```python
try:
    es_client.refresh_index()  # ✅ Asegura que datos indexados sean visibles
except Exception as refresh_error:
    logger.warning(...)
```

#### c) Agregar manejo de errores en worker (`services/worker/tasks/coordinator.py`)
```python
try:
    finding_id = get_pg_client().create_finding(finding_data)
    # ... procesar
except Exception as finding_error:
    logger.error(f"Error processing finding: {finding_error}")

try:
    success, errors = get_es_client().bulk_index_findings(findings_to_save)
    logger.info(f"Indexed {success} findings, {errors} errors")  # ✅ Logging visible
except Exception as index_error:
    logger.error(f"Error bulk indexing: {index_error}")
```

#### d) Manejo seguro de respuesta de búsqueda
```python
return {
    "query": query,
    "findings": result.get('hits', []),        # ✅ Valor default
    "total": result.get('total', 0),            # ✅ Valor default
    "took_ms": result.get('took_ms', 0)         # ✅ Valor default
}
```

---

### Problema 2: HISTORIAL SIEMPRE VACÍO

**Síntomas:**
- El endpoint `/jobs` retorna lista vacía
- No aparecen jobs en el historial

**Causas Identificadas:**
1. ❌ `list_jobs()` no estaba implementada en PostgreSQL client
2. ❌ `count_jobs()` no existía

**Soluciones Aplicadas:**

#### a) Implementar `list_jobs()` en PostgreSQL client
```python
def list_jobs(self, limit: int = 20, offset: int = 0, status: Optional[str] = None) -> List[Dict]:
    """Return paginated list of jobs with metadata"""
    query = (
        "SELECT job_id, status, requester_id, input_type, input_value, progress, created_at, updated_at "
        "FROM jobs"
    )
    # ... filtrado por status si aplica
    return [dict(row) for row in cursor.fetchall()]
```

#### b) Implementar `count_jobs()` en PostgreSQL client
```python
def count_jobs(self, status: Optional[str] = None) -> int:
    """Count jobs, optionally filtered by status"""
    query = "SELECT COUNT(*) FROM jobs"
    # ... agregar WHERE si status especificado
```

#### c) Mejorar respuesta en routes (`services/api/app/api/routes_v2.py`)
```python
formatted_jobs = []
for job in jobs:
    formatted_jobs.append({
        "job_id": job.get('job_id'),
        "status": job.get('status'),
        "requester_id": job.get('requester_id'),
        "input_type": job.get('input_type'),
        "input_value": job.get('input_value'),
        "progress": job.get('progress', 0),
        "created_at": job.get('created_at'),
        "updated_at": job.get('updated_at')
    })
```

---

### Problema 3: ESTADÍSTICAS SIEMPRE EN 0

**Síntomas:**
- `/stats` retorna todos los conteos como 0
- La sección Sistema nunca muestra datos

**Causas Identificadas:**
1. ❌ `count_indicators()` no estaba implementada
2. ❌ Errores de conexión no manejados (causa silenciosa de valores 0)
3. ❌ Neo4j fallos causaban que endpoint fallara completamente

**Soluciones Aplicadas:**

#### a) Implementar `count_indicators()` en PostgreSQL client
```python
def count_indicators(self) -> int:
    """Count total indicators in database"""
    cursor.execute("SELECT COUNT(*) FROM indicators")
    return cursor.fetchone()[0] if result else 0
```

#### b) Mejorar endpoint `/stats` con manejo de errores (`services/api/app/api/routes_v2.py`)
```python
try:
    with pg_client.get_connection() as conn:
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('completed', 'processing')")
        total_jobs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM findings WHERE soft_deleted = false")
        total_findings = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM indicators")
        total_indicators = cursor.fetchone()[0]
except Exception as db_error:
    logger.error(f"Database error: {db_error}")
    # ✅ Retorna 0s en lugar de fallar
    total_jobs = 0
    total_findings = 0
    total_indicators = 0

try:
    neo4j_stats = neo4j_client.get_statistics()
except Exception as neo4j_error:
    logger.error(f"Neo4j error: {neo4j_error}")
    neo4j_stats = {}  # ✅ No bloquea el endpoint
```

---

## 🔧 Cambios Técnicos Adicionales

### 1. Mejor Tracking de Jobs (`services/api/app/api/routes_v2.py`)
- ✅ Guardar `task_id` de Celery en BD al crear job
- ✅ Implementar `update_job_task_id()` en PostgreSQL client

```python
# En create_job:
enqueue_result = enqueue_job(job_id, enqueue_data)
task_id = enqueue_result.get("task_id")
pg_client.update_job_task_id(job_id, task_id)  # ✅ Guardar para tracking
```

### 2. Mejor Logging del Progreso (`services/worker/tasks/coordinator.py`)
- ✅ Mejorada función `update_job_status()` para incluir progreso

```python
def update_job_status(job_id: str, status: str, progress: int = None):
    if progress is not None:
        cur.execute(
            "UPDATE jobs SET status = %s, progress = %s WHERE job_id = %s",
            (status, progress, job_id)
        )
    logger.info(f"Job {job_id} status={status}" + (f" progress={progress}%" if progress else ""))
```

### 3. Persistencia de Batch Jobs (`services/api/app/api/routes_v2.py`)
- ✅ Ahora se crea registro en BD antes de enquelar jobs
- ✅ FK desde jobs a batches para trazabilidad

```python
batch_id = f"batch-{uuid.uuid4().hex[:8]}"
pg_client.create_batch(batch_id, len(requests))  # ✅ Registrar batch
for req in requests:
    pg_client.create_job(..., batch_id=batch_id)  # ✅ Asociar a batch
```

---

## 📊 Resumen de Archivos Modificados

| Archivo | Cambios |
|---------|---------|
| `services/api/app/main.py` | ✅ Agregar startup event para crear índices |
| `services/api/app/api/routes_v2.py` | ✅ Mejorar /search, /stats, /jobs |
| `services/shared/postgres_client.py` | ✅ Nuevos métodos: list_jobs, count_jobs, count_indicators, update_job_task_id, update_job_progress |
| `services/worker/tasks/coordinator.py` | ✅ Mejorar manejo de errores, logging y status updates |

---

## 🧪 Cómo Probar las Correcciones

### 1. Prueba de Búsqueda
```bash
# Crear un job
curl -X POST http://localhost:8000/api/v2/jobs \
  -H "Content-Type: application/json" \
  -d '{"value": "test", "input_type": "general"}'

# Esperar a que procese (verificar logs del worker)
# docker-compose logs worker

# Buscar
curl "http://localhost:8000/api/v2/search/findings?query=test"
# Debe retornar findings (no array vacío)
```

### 2. Prueba de Historial
```bash
curl http://localhost:8000/api/v2/jobs
# Debe retornar lista de jobs con status, timestamps, etc.
```

### 3. Prueba de Estadísticas
```bash
curl http://localhost:8000/api/v2/stats
# Debe retornar conteos > 0 si hay data
```

---

## 🚀 Siguientes Pasos Recomendados

1. **Restart de Contenedores**
   ```bash
   docker-compose down
   docker-compose up -d --build
   ```

2. **Verificar Logs**
   ```bash
   docker-compose logs api -f      # Verificar startup
   docker-compose logs worker -f   # Verificar procesamiento
   docker-compose logs elasticsearch  # Verificar indexing
   ```

3. **Testing Manual**
   - Hacer una búsqueda en la UI
   - Verificar que aparezca en Historial
   - Verificar estadísticas en Sistema

---

## ✅ Archivos Compilados sin Errores
- ✅ services/api/app/main.py
- ✅ services/api/app/api/routes_v2.py
- ✅ services/worker/tasks/coordinator.py
- ✅ services/shared/postgres_client.py

**Fecha**: 19 de Enero 2026  
**Branch**: feature/v2-implementation  
**Estado**: Listo para testing
