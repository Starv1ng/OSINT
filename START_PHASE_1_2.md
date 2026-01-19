# 🚀 SIGUIENTE: FASE 1-2 - COMENZAR AQUÍ

**Documento**: Instrucciones para continuar desde Fase 0  
**Rama Actual**: `feature/v2-implementation`  
**Estado Fase 0**: ✅ COMPLETADA  
**Duración Estimada Fase 1-2**: 2-3 semanas (1-2 engineers)  

---

## 📌 ANTES DE COMENZAR

**Revisar estos documentos (5 min)**:
1. ✅ `OSINT_v2.0_IMPLEMENTATION_GUIDE.md` - Guía completa (secciones 3-4)
2. ✅ `PHASE_0_FINAL_REPORT.md` - Estado actual + checklist
3. ✅ Este documento

**Verificar estado**:
```bash
git branch -v              # Confirmar en feature/v2-implementation
docker-compose ps          # Confirmar servicios activos
git log --oneline -3       # Ver últimos commits
```

---

## 🎯 FASE 1-2 EN 4 PASOS

### PASO 1: Crear Esquema PostgreSQL v2.0 (Día 1-2)

**Archivo a crear**: `infra/init_db_v2.sql`
**Referencia**: `OSINT_v2.0_IMPLEMENTATION_GUIDE.md` Sección 3

**Tabla 1: findings** - Core de hallazgos OSINT
```sql
CREATE TABLE findings (
    finding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    module_run_id UUID,
    module_name TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    relevance_score FLOAT CHECK (relevance_score >= 0 AND relevance_score <= 1),
    source_url TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_findings_job_id ON findings(job_id);
CREATE INDEX idx_findings_module_name ON findings(module_name);
CREATE INDEX idx_findings_confidence ON findings(confidence DESC);
```

**Tabla 2: indicators** - Indicadores extraídos
```sql
CREATE TABLE indicators (
    indicator_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID NOT NULL REFERENCES findings(finding_id) ON DELETE CASCADE,
    type VARCHAR(30) NOT NULL,  -- email, phone, username, domain, ip, etc.
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    confidence FLOAT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_indicators_finding_id ON indicators(finding_id);
CREATE INDEX idx_indicators_type ON indicators(type);
CREATE INDEX idx_indicators_normalized_value ON indicators(normalized_value);
```

**Tabla 3: entity_references** - Referencias a entidades
```sql
CREATE TABLE entity_references (
    entity_ref_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID NOT NULL REFERENCES findings(finding_id) ON DELETE CASCADE,
    entity_name TEXT NOT NULL,
    entity_type VARCHAR(50) NOT NULL,  -- person, organization, location, etc.
    confidence FLOAT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_entity_references_finding_id ON entity_references(finding_id);
CREATE INDEX idx_entity_references_entity_name ON entity_references(entity_name);
```

**Tabla 4: module_runs** - Ejecución de módulos
```sql
CREATE TABLE module_runs (
    module_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    module_name TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,  -- started, completed, failed
    findings_count INT DEFAULT 0,
    indicators_count INT DEFAULT 0,
    duration_ms INT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_module_runs_job_id ON module_runs(job_id);
CREATE INDEX idx_module_runs_module_name ON module_runs(module_name);
```

**Tabla 5-10**: (Ver guía completa para execution_metrics, data_lineage, job_deduplication, audit_log, system_config, indicators_relationships)

**Checklist Paso 1**:
- [ ] Archivo `infra/init_db_v2.sql` creado con 10 tablas
- [ ] Archivo `infra/init_db_v2.sql` testeado en contenedor
- [ ] Todas las tablas tienen índices críticos
- [ ] Foreign keys funcionan correctamente
- [ ] Seed data inicial cargado (jobs table vacía)
- [ ] Commit: `git commit -m "feat(db): create v2.0 schema with 10 normalized tables"`

---

### PASO 2: Crear Elasticsearch Mappings v2.0 (Día 2-3)

**Archivo a crear**: `infra/elasticsearch_init.py` o `elasticsearch_init.sh`

**Índice 1: findings-v2**
```json
{
  "mappings": {
    "properties": {
      "finding_id": { "type": "keyword" },
      "job_id": { "type": "keyword" },
      "module_name": { "type": "keyword" },
      "type": { "type": "keyword" },
      "value": { "type": "text", "analyzer": "standard" },
      "normalized_value": { "type": "keyword" },
      "confidence": { "type": "float" },
      "relevance_score": { "type": "float" },
      "created_at": { "type": "date" },
      "updated_at": { "type": "date" },
      "metadata": { "type": "object", "enabled": true }
    }
  },
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "index.lifecycle.name": "findings-ilm-policy"
  }
}
```

**ILM Policy**: 7d hot → 30d warm → 90d cold → delete

**Checklist Paso 2**:
- [ ] 3 índices Elasticsearch v2.0 creados (findings, module_runs, metrics)
- [ ] ILM policies configuradas
- [ ] Mappings testeados (curl GET _mapping)
- [ ] Shards y replicas configurados
- [ ] Commit: `git commit -m "feat(elasticsearch): add v2.0 mappings with ILM policies"`

---

### PASO 3: Inicializar Neo4j (Día 3-4)

**Archivo a crear**: `infra/neo4j_init.cypher`

**Constraints y Índices**:
```cypher
-- Entity constraints
CREATE CONSTRAINT entity_unique_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;
CREATE CONSTRAINT entity_unique_name_type IF NOT EXISTS FOR (e:Entity) REQUIRE (e.name, e.type) IS UNIQUE;

-- Finding constraints
CREATE CONSTRAINT finding_unique_id IF NOT EXISTS FOR (f:Finding) REQUIRE f.finding_id IS UNIQUE;

-- Job constraint
CREATE CONSTRAINT job_unique_id IF NOT EXISTS FOR (j:Job) REQUIRE j.job_id IS UNIQUE;

-- Indices
CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type);
CREATE INDEX entity_source IF NOT EXISTS FOR (e:Entity) ON (e.source);
CREATE INDEX finding_job_id IF NOT EXISTS FOR (f:Finding) ON (f.job_id);
```

**Checklist Paso 3**:
- [ ] Archivo `infra/neo4j_init.cypher` creado
- [ ] Constraints aplicadas en Neo4j
- [ ] Índices verificados (`:schema` en Neo4j browser)
- [ ] Test: crear un nodo Entity y verificar constraint
- [ ] Commit: `git commit -m "feat(neo4j): initialize graph database with constraints and indices"`

---

### PASO 4: Crear Clientes Python (Día 4-7)

**Archivo 1: `services/shared/postgres_client.py`** (~200 líneas)

```python
from typing import List, Dict, Optional, Any
from psycopg2.pool import SimpleConnectionPool
import json
from datetime import datetime
import logging

class PostgreSQLClient:
    def __init__(self, connection_string: str, pool_size: int = 10):
        self.pool = SimpleConnectionPool(1, pool_size, connection_string)
        self.logger = logging.getLogger(__name__)
    
    def create_finding(self, job_id: str, finding_data: Dict) -> str:
        """Create finding and return finding_id"""
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO findings (job_id, module_name, type, value, 
                    normalized_value, confidence, relevance_score, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING finding_id
            """, (
                job_id, finding_data['module_name'], finding_data['type'],
                finding_data['value'], finding_data['normalized_value'],
                finding_data.get('confidence'), finding_data.get('relevance_score'),
                json.dumps(finding_data.get('metadata', {}))
            ))
            finding_id = cursor.fetchone()[0]
            conn.commit()
            return str(finding_id)
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Error creating finding: {e}")
            raise
        finally:
            self.pool.putconn(conn)
    
    def get_findings(self, job_id: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get findings for a job"""
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT finding_id, job_id, module_name, type, value, 
                    normalized_value, confidence, relevance_score, created_at
                FROM findings
                WHERE job_id = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (job_id, limit, offset))
            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
        finally:
            self.pool.putconn(conn)
    
    def check_dedup_exists(self, job_id: str, finding_hash: str) -> bool:
        """Check if finding already exists for deduplication"""
        # Implementar lógica de deduplicación
        pass
    
    def create_indicator(self, finding_id: str, indicator_data: Dict) -> str:
        """Create indicator linked to finding"""
        # Implementar creación de indicador
        pass
```

**Archivo 2: `services/shared/elasticsearch_client.py`** (~250 líneas)

**Archivo 3: `services/shared/neo4j_client.py`** (~300 líneas)

**Checklist Paso 4**:
- [ ] PostgreSQL Client: CRUD completo, transaction support, tests
- [ ] Elasticsearch Client: Bulk indexing, search, aggregations, tests
- [ ] Neo4j Client: Entity ops, relationships, graph queries, tests
- [ ] Todos los clientes tienen unit tests pasando
- [ ] Integración: Clientes se importan desde `services/shared/`
- [ ] Commit: `git commit -m "feat(clients): implement PostgreSQL, Elasticsearch, and Neo4j clients"`

---

## 📊 CHECKLIST COMPLETO FASE 1-2

### Prerequisitos
- [ ] Rama `feature/v2-implementation` activa
- [ ] Servicios Docker activos (postgres, elasticsearch, neo4j, minio)
- [ ] `OSINT_v2.0_IMPLEMENTATION_GUIDE.md` revisado

### PostgreSQL
- [ ] `infra/init_db_v2.sql` creado con 10 tablas
- [ ] Todas las tablas tienen índices críticos (8+ índices)
- [ ] Foreign keys configurados
- [ ] Probado: crear findings, indicadores, módulo_runs
- [ ] Probado: deduplicación 3-level

### Elasticsearch
- [ ] 3 índices v2.0 creados
- [ ] ILM policies configuradas (hot/warm/cold)
- [ ] Mappings verificados
- [ ] Probado: indexar 1000+ documentos
- [ ] Probado: búsqueda full-text

### Neo4j
- [ ] Constraints creados
- [ ] Índices verificados
- [ ] Probado: crear nodos, relaciones
- [ ] Probado: shortest-path algorithm

### MinIO
- [ ] 2 buckets creados (osint-findings, osint-exports)
- [ ] Lifecycle policies configuradas
- [ ] Probado: upload/download de objetos

### Clientes Python
- [ ] PostgreSQL Client: 100% funcional
- [ ] Elasticsearch Client: 100% funcional
- [ ] Neo4j Client: 100% funcional
- [ ] Todos con unit tests: 90%+ coverage
- [ ] Integración: importables desde services/shared/

### Documentación
- [ ] Actualizar OSINT_v2.0_IMPLEMENTATION_GUIDE.md con learnings
- [ ] Documentar cambios en `infra/`
- [ ] README actualizado con instrucciones v2.0

---

## 🔄 COMANDOS ÚTILES

```bash
# Ver estado de rama
git branch -v
git log --oneline -5

# Ver servicios
docker-compose ps

# Acceder a PostgreSQL
docker-compose exec postgres psql -U dev -d osint

# Acceder a Neo4j browser
open http://localhost:7474

# Ver Elasticsearch
curl http://localhost:9200/_cat/indices

# Subir cambios
git add .
git commit -m "feat(phase-1): [descripción]"
git push origin feature/v2-implementation
```

---

## 🎯 ESTIMADO DE TIEMPO

- **Paso 1** (PostgreSQL schema): 1-2 días
- **Paso 2** (Elasticsearch): 1 día
- **Paso 3** (Neo4j): 1 día
- **Paso 4** (Clientes Python): 3-4 días
- **Testing & Documentation**: 2-3 días

**Total Fase 1-2**: 8-12 días (1-2 semanas con 1 engineer)

---

## ❓ PREGUNTAS FRECUENTES

**P: ¿Qué pasa si algo falla?**
A: Rollback disponible en `BACKUP_v1_20260119_030919`. Ver `PHASE_0_FINAL_REPORT.md` para instrucciones.

**P: ¿Necesito cambiar docker-compose.yml?**
A: No. Los servicios ya están configurados. Solo crear las tablas/índices/constraints.

**P: ¿Cuándo paso a Fase 3-4?**
A: Cuando todos los pasos 1-4 estén completados, testeados, y los commits estén en git.

**P: ¿Puedo hacer cambios al esquema durante Fase 1-2?**
A: Sí, pero documenta los cambios. Actualiza `init_db_v2.sql` para que otros engineers puedan replicar.

---

## 📞 SIGUIENTE COMMIT

```bash
git commit -m "feat(phase-1-2): implement v2.0 database layer and clients

- Create 10 normalized PostgreSQL tables
- Setup Elasticsearch v2.0 mappings with ILM
- Initialize Neo4j graph database
- Implement PostgreSQL, Elasticsearch, Neo4j clients
- Add comprehensive unit tests for all clients
- Update documentation and deployment guides"
```

---

**¡Listo para comenzar Fase 1-2!** 🚀

Cuando tengas los pasos 1-4 completados, confirma en git y estarás listo para Fase 3-4 (API & Workers).
