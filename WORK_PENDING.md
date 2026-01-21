# Trabajo Pendiente - OSINT Project v2

## Problemas Identificados pero No Corregidos Aún

### P1: Duplicación en Settings
**Archivo**: Múltiples en `services/worker/tasks/modules/`
**Problema**: Ambiente variables leídas en múltiples lugares
**Solución recomendada**: Centralizar en un módulo `config.py` único

**Estado**: ⏳ PENDIENTE

---

### P2: Circular Imports Potenciales
**Archivos**: 
- `services/worker/tasks/es_client.py`
- `services/worker/tasks/dynamic_orchestrator.py`
- `services/worker/tasks/coordinator.py`

**Problema**: Cross-imports complejos
**Solución recomendada**: Dependency injection en lugar de imports locales

**Estado**: ⏳ PENDIENTE

---

### P3: Retry Logic No Implementada
**Ubicación**: `services/worker/tasks/coordinator.py`
**Problema**: Sin exponential backoff en reintentos
**Solución recomendada**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def enqueue_job_with_retry(job_id, data):
    pass
```

**Estado**: ⏳ PENDIENTE

---

### P4: Logging Inconsistente
**Archivos**: Múltiples
**Problema**: Formatos de log diferentes, algunos sin contexto
**Solución recomendada**: Unified logging con Structlog

**Estado**: ⏳ PENDIENTE

---

### P5: Validación de Entrada Débil
**Archivos**: `services/api/app/api/routes_v2.py`
**Problema**: Muchos endpoints confían en validación de Pydantic solamente
**Solución recomendada**: Agregar validaciones custom en modelos

**Ejemplos**:
- `IngestRequest.value` - sin límite de largo
- `QueryParams` - sin whitelist de módulos
- `BatchRequest` - sin validación de job_ids existentes

**Estado**: ⏳ PENDIENTE

---

### P6: Caching No Implementado
**Endpoints de Alto Acceso**:
- `/system/stats` - podría cachearse por 60s
- `/available-modules` - estático, cache permanente
- `/jobs/{job_id}` - cache invalidable

**Estado**: ⏳ PENDIENTE

---

### P7: Rate Limiting Ausente
**Problema**: Sin límites de tasa en endpoints críticos
**Solución recomendada**:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/jobs")
@limiter.limit("10/minute")
def create_job(...):
    pass
```

**Estado**: ⏳ PENDIENTE

---

### P8: Error Handling Genérico
**Problema**: Muchos `except Exception` sin clasificación
**Solución recomendada**: 
```python
try:
    ...
except ValidationError as e:
    raise HTTPException(status_code=422, detail=str(e))
except DatabaseError as e:
    raise HTTPException(status_code=503, detail="Database unavailable")
except ConnectionError as e:
    raise HTTPException(status_code=504, detail="Service unavailable")
except Exception as e:
    logger.critical(f"Unexpected error: {e}")
    raise HTTPException(status_code=500, detail="Internal error")
```

**Estado**: ⏳ PENDIENTE

---

### P9: Tests Faltantes
**Archivos sin cobertura**: Todos los archivos corregidos
**Requerimientos**:
- Unit tests para `create_job` (rollback path)
- Unit tests para `pause_job` (revoke path)
- Integration tests para rutas consolidadas
- Mock tests para dynamic_orchestrator pause checking

**Estado**: ⏳ PENDIENTE

---

### P10: Documentación de API
**Problema**: Endpoints sin docstrings completos
**Faltantes**: 
- Descripción de parámetros
- Ejemplos de response
- Códigos de error documentados

**Estado**: ⏳ PENDIENTE

---

## Prioridades de Corrección

### 🔴 CRÍTICO (Próxima sesión)
1. **P2: Circular Imports** - Puede causar errores de runtime
2. **P3: Retry Logic** - Falla sin reintentos automáticos
3. **P1: Settings Centralizados** - Facilita debugging

### 🟡 IMPORTANTE (1-2 semanas)
1. **P8: Error Handling** - Mejor debugging
2. **P9: Tests** - Validar correcciones
3. **P5: Validación de Entrada** - Seguridad

### 🟢 NICE-TO-HAVE (Futuro)
1. **P4: Logging Consistente** - Observabilidad
2. **P6: Caching** - Performance
3. **P7: Rate Limiting** - Protección
4. **P10: Documentación** - Usabilidad

---

## Cómo Continuar

Para agregar estas correcciones:

```bash
# 1. Crear branch para P2
git checkout -b feature/fix-circular-imports

# 2. Resolver imports en:
#    - services/worker/tasks/es_client.py
#    - services/worker/tasks/dynamic_orchestrator.py
#    - services/worker/tasks/coordinator.py

# 3. Testear
python -m pytest services/worker/tests/

# 4. Commit & Push
git add .
git commit -m "fix: resolve circular imports in worker tasks"
git push origin feature/fix-circular-imports

# 5. Create PR
# En GitHub: base=feature/v2-implementation <- compare=feature/fix-circular-imports
```

---

## Notas de Context para Futuro

- **Branch**: feature/v2-implementation en Starv1ng/OSINT
- **Codebase**: OSINT project con FastAPI + Celery + PostgreSQL + Elasticsearch + Neo4j
- **Análisis previo**: Ver `TECHNICAL_ANALYSIS.md` para detalles completos
- **Cambios recientes**: Ver `CORRECTIONS_EXECUTED.md` para lo que ya fue hecho
- **Estado general**: V2 migration parcialmente completada, legacy code aún presente en algunos módulos

---

**Última actualización**: 2025-01-19
**Sesión anterior completó**: Phase 1-4 (código muerto, rutas duplicadas, mock data, error handling)
**Este documento mantiene**: Backlog de trabajo futuro
