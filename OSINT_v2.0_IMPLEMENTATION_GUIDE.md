# 🚀 OSINT v2.0 - GUÍA DE IMPLEMENTACIÓN COMPLETA

**Documento**: OSINT_v2.0_IMPLEMENTATION_GUIDE.md  
**Propósito**: Guía unificada para Copilot - Implementar completamente v2.0  
**Estado**: FINAL - LISTO PARA EJECUTAR  
**Fecha**: January 2026  
**Tiempo Estimado**: 6-8 semanas (2-3 engineers)

---

## ÍNDICE RÁPIDO

- [1. ARQUITECTURA GENERAL](#1-arquitectura-general)
- [2. STACK TECNOLÓGICO](#2-stack-tecnológico)
- [3. SCHEMA DATABASE](#3-schema-database)
- [4. IMPLEMENTACIÓN FASE 1-2](#4-implementación-fase-1-2-database--clients)
- [5. IMPLEMENTACIÓN FASE 3-4](#5-implementación-fase-3-4-api--workers)
- [6. IMPLEMENTACIÓN FASE 5](#6-implementación-fase-5-frontend)
- [7. CHECKLISTS](#7-checklists)

---

## 1. ARQUITECTURA GENERAL

### Visión General

```
PROBLEMA (v1.0):
├─ Neo4j + MinIO sin usar
├─ PostgreSQL minimal (1 tabla)
├─ Elasticsearch insuficiente
├─ API limitada (~15 endpoints)
├─ Sin real-time updates
└─ Deduplicación débil

SOLUCIÓN (v2.0):
├─ Stack completo integrado (PostgreSQL + ES + Neo4j + MinIO + Redis)
├─ 36 endpoints REST + WebSocket
├─ Deduplicación 3-level (99.9%)
├─ Correlación de entidades via Neo4j
├─ Cache 3-tier para performance
└─ Escalabilidad horizontal
```

### Componentes

```
WEB TIER (Stateless)
├─ FastAPI service
├─ 3-5 replicas (load balanced)
├─ 36 REST endpoints + 1 WebSocket
└─ JWT authentication

WORKER TIER (Stateless)
├─ Celery workers (5-20 replicas, auto-scaling)
├─ 3 priority queues (high, default, low)
├─ Module execution + correlation
└─ Metrics collection

DATA TIER (Managed)
├─ PostgreSQL (10 tables, master + replicas)
├─ Elasticsearch (3 indices, sharded)
├─ Neo4j (Entity graph, causal cluster)
├─ MinIO (Object storage, distributed)
└─ Redis (Messaging + Cache)
```

### Flujo de Datos

```
USER → API (POST /jobs) → PostgreSQL (save job)
       → Redis (enqueue task)
       → Celery Worker (execute search)
          ├─ Run modules (concurrent)
          ├─ Index to Elasticsearch (async)
          ├─ Save to PostgreSQL (atomic)
          ├─ Extract indicators
          ├─ Create Neo4j entities
          ├─ Publish to Redis Streams
          └─ API → WebSocket → Browser (real-time)
       → Cache (L1: Redis, L2: PG, L3: ES)
       → User views results via dashboard
```

---

## 2. STACK TECNOLÓGICO

### Base de Datos

| Servicio | Versión | Propósito | Justificación |
|----------|---------|----------|--------------|
| PostgreSQL | 15+ | Transactional data | ACID consistency, dedup, audit log |
| Elasticsearch | 8.10.2+ | Full-text search | Sub-second queries, aggregations, analytics |
| Neo4j | 5+ | Graph database | Entity correlations, shortest path, algorithms |
| MinIO | latest | Object storage | Raw content, exports, S3-compatible |
| Redis | 7+ | Message broker + cache | Celery, WebSocket, session, L1 cache |

### Application Stack

| Layer | Framework | Justificación |
|-------|-----------|--------------|
| API | FastAPI | Async/await, OpenAPI, type safety, 3x faster than Flask |
| Workers | Celery + Redis | Distributed execution, retry logic, monitoring |
| Frontend | Vue/React + D3.js | Modern, interactive visualizations |
| Container | Docker + Compose | Reproducible environments, easy scaling |

### Modelos de Datos

**PostgreSQL** (10 tablas):
```
Core:        findings, indicators, entity_references, module_runs
Tracking:    execution_metrics, data_lineage
Quality:     job_deduplication
Compliance:  audit_log, system_config
```

**Elasticsearch** (3 índices):
```
findings       - Full-text search, facets, aggregations
module_runs    - Module execution metrics
metrics        - System-wide performance data
```

**Neo4j** (8 node types):
```
Entity, Finding, Job, Analyst, Location, Organization, Event, Evidence
```

---

## 3. SCHEMA DATABASE

### PostgreSQL: SQL Completo

```sql
-- ============================================================
-- CORE TABLES
-- ============================================================

CREATE TABLE findings (
    finding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    module_run_id UUID REFERENCES module_runs(module_run_id),
    module_name TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    relevance_score FLOAT CHECK (relevance_score >= 0 AND relevance_score <= 1),
    verified BOOLEAN DEFAULT false,
    verified_by UUID,
    verified_at TIMESTAMP,
    iteration INT DEFAULT 1,
    source_url TEXT,
    raw_text TEXT,
    metadata JSONB DEFAULT '{}',
    tags TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    soft_deleted BOOLEAN DEFAULT false,
    dup_of_id UUID REFERENCES findings(finding_id),
    created_by TEXT
);

CREATE TABLE indicators (
    indicator_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(50) NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL UNIQUE,
    data_type VARCHAR(20),
    source_finding_id UUID REFERENCES findings(finding_id),
    confidence FLOAT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    occurrence_count INT DEFAULT 1,
    created_by TEXT
);

CREATE TABLE entity_references (
    reference_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    indicator_id UUID NOT NULL REFERENCES indicators(indicator_id),
    finding_id UUID NOT NULL REFERENCES findings(finding_id),
    context TEXT,
    position INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE module_runs (
    module_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    module_name TEXT NOT NULL,
    module_version TEXT,
    status VARCHAR(20),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    duration_ms INT,
    items_processed INT,
    findings_count INT,
    errors TEXT,
    raw_result JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TRACKING TABLES
-- ============================================================

CREATE TABLE execution_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_run_id UUID NOT NULL REFERENCES module_runs(module_run_id),
    metric_name VARCHAR(100),
    metric_value FLOAT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE data_lineage (
    lineage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_finding_id UUID REFERENCES findings(finding_id),
    derived_finding_id UUID REFERENCES findings(finding_id),
    transformation TEXT,
    iteration INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE indicators_relationships (
    relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    indicator_id_1 UUID NOT NULL REFERENCES indicators(indicator_id),
    indicator_id_2 UUID NOT NULL REFERENCES indicators(indicator_id),
    relationship_type TEXT,
    confidence FLOAT,
    evidence TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(indicator_id_1, indicator_id_2, relationship_type)
);

-- ============================================================
-- QUALITY & COMPLIANCE TABLES
-- ============================================================

CREATE TABLE job_deduplication (
    dedup_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    indicator_hash TEXT NOT NULL,
    finding_id UUID NOT NULL REFERENCES findings(finding_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, indicator_hash)
);

CREATE TABLE audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    action VARCHAR(100),
    resource_type VARCHAR(50),
    resource_id TEXT,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE system_config (
    config_id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value JSONB,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

-- ============================================================
-- INDICES (CRITICAL FOR PERFORMANCE)
-- ============================================================

CREATE INDEX idx_findings_job_id ON findings(job_id);
CREATE INDEX idx_findings_type ON findings(type);
CREATE INDEX idx_findings_confidence ON findings(confidence DESC);
CREATE INDEX idx_findings_created_at ON findings(created_at DESC);
CREATE INDEX idx_findings_normalized_value ON findings(normalized_value);
CREATE INDEX idx_findings_status ON findings(verified, soft_deleted);

CREATE INDEX idx_indicators_normalized_value ON indicators(normalized_value);
CREATE INDEX idx_indicators_type ON indicators(type);
CREATE INDEX idx_indicators_finding_id ON indicators(source_finding_id);

CREATE INDEX idx_module_runs_job_id ON module_runs(job_id);
CREATE INDEX idx_module_runs_status ON module_runs(status);
CREATE INDEX idx_module_runs_created_at ON module_runs(created_at DESC);

CREATE INDEX idx_audit_log_timestamp ON audit_log(created_at DESC);
CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_resource ON audit_log(resource_type, resource_id);

CREATE UNIQUE INDEX idx_job_dedup ON job_deduplication(job_id, indicator_hash);
```

### Elasticsearch Mappings

```python
ES_FINDINGS_MAPPING = {
    "mappings": {
        "properties": {
            "finding_id": {"type": "keyword"},
            "job_id": {"type": "keyword"},
            "module_run_id": {"type": "keyword"},
            "module_name": {"type": "keyword"},
            "type": {"type": "keyword"},
            "value": {"type": "text", "analyzer": "standard", "fields": {"keyword": {"type": "keyword"}}},
            "normalized_value": {"type": "keyword"},
            "confidence": {"type": "float"},
            "relevance_score": {"type": "float"},
            "verified": {"type": "boolean"},
            "iteration": {"type": "integer"},
            "source_url": {"type": "keyword"},
            "raw_text": {"type": "text", "analyzer": "standard"},
            "metadata": {"type": "nested"},
            "tags": {"type": "keyword"},
            "timestamp": {"type": "date"},
            "created_at": {"type": "date"},
            "extracted_indicators": {"type": "nested"}
        }
    },
    "settings": {
        "number_of_shards": 3,
        "number_of_replicas": 2,
        "index.codec": "best_compression",
        "index.refresh_interval": "30s"
    }
}

# Create index
es_client.indices.create(index="findings-000001", body=ES_FINDINGS_MAPPING, ignore=[400])
```

### Neo4j Model

```cypher
-- Create constraints
CREATE CONSTRAINT entity_unique IF NOT EXISTS FOR (e:Entity) REQUIRE (e.id, e.type) IS UNIQUE;
CREATE CONSTRAINT finding_unique IF NOT EXISTS FOR (f:Finding) REQUIRE f.finding_id IS UNIQUE;
CREATE CONSTRAINT job_unique IF NOT EXISTS FOR (j:Job) REQUIRE j.job_id IS UNIQUE;

-- Create indices
CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type);
CREATE INDEX finding_job_index IF NOT EXISTS FOR (f:Finding) ON (f.job_id);
```

---

## 4. IMPLEMENTACIÓN FASE 1-2: DATABASE & CLIENTS

### Fase 0: Preparación (Semana 1)

**Tareas**:
1. Crear branch: `git checkout -b develop-v2-implementation`
2. Backup PostgreSQL: `pg_dump osint_db > backup_$(date +%Y%m%d).sql`
3. Backup Elasticsearch: Snapshot to MinIO
4. Crear docker-compose.v2.yml (actualizar versiones)
5. Test connectivity a todos los servicios

### Fase 1: Database Layer (Semana 2-3)

**Tarea 1.1**: PostgreSQL Schema
```bash
# Crear test database
createdb osint_v2_test

# Ejecutar SQL completo (ver sección 3)
psql -U osint_user -d osint_v2_test -f schema_v2.sql

# Verificar tablas
psql -U osint_user -d osint_v2_test -c "\dt"

# Verificar índices
psql -U osint_user -d osint_v2_test -c "\di"
```

**Tarea 1.2**: Elasticsearch Setup
```python
from elasticsearch import Elasticsearch

es = Elasticsearch(["localhost:9200"])

# Create mapping
es.indices.create(index="findings-000001", body=ES_FINDINGS_MAPPING, ignore=[400])

# Verify
print(es.indices.get(index="findings-000001"))
```

**Tarea 1.3**: Neo4j Init
```cypher
# Run in Neo4j Browser
CREATE CONSTRAINT entity_unique IF NOT EXISTS FOR (e:Entity) REQUIRE (e.id, e.type) IS UNIQUE;
CREATE CONSTRAINT finding_unique IF NOT EXISTS FOR (f:Finding) REQUIRE f.finding_id IS UNIQUE;
CREATE CONSTRAINT job_unique IF NOT EXISTS FOR (j:Job) REQUIRE j.job_id IS UNIQUE;

# Verify
CALL db.constraints();
```

**Tarea 1.4**: MinIO Setup
```python
from minio import Minio

minio = Minio("localhost:9000", "minioadmin", "minioadmin", secure=False)

buckets = ["osint-raw-content", "osint-exports", "osint-backups"]
for bucket in buckets:
    if not minio.bucket_exists(bucket):
        minio.make_bucket(bucket)
```

### Fase 2: Clients Refactor (Semana 3-4)

**Tarea 2.1**: PostgreSQL Client

```python
# services/shared/db_client.py

from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional, Dict, List

class PostgreSQLClient:
    def __init__(self, database_url: str):
        self.engine = create_engine(
            database_url,
            poolclass=pool.QueuePool,
            pool_size=20,
            max_overflow=40,
            pool_pre_ping=True
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def create_finding(self, finding_data: Dict) -> str:
        """Insert finding and return ID"""
        session: Session = self.SessionLocal()
        try:
            from models import Finding
            finding = Finding(**finding_data)
            session.add(finding)
            session.commit()
            return str(finding.finding_id)
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_findings(self, job_id: str, filters: Optional[Dict] = None, limit: int = 100) -> List[Dict]:
        """Query findings with filters"""
        session: Session = self.SessionLocal()
        try:
            from models import Finding
            query = session.query(Finding).filter(Finding.job_id == job_id)
            
            if filters:
                if 'type' in filters:
                    query = query.filter(Finding.type.in_(filters['type']))
                if 'confidence_min' in filters:
                    query = query.filter(Finding.confidence >= filters['confidence_min'])
                if 'verified' in filters:
                    query = query.filter(Finding.verified == filters['verified'])
            
            results = query.limit(limit).all()
            return [r.to_dict() for r in results]
        finally:
            session.close()
    
    def check_dedup_exists(self, job_id: str, indicator_hash: str) -> bool:
        """Check if indicator exists for job"""
        session: Session = self.SessionLocal()
        try:
            from models import JobDeduplication
            exists = session.query(JobDeduplication).filter(
                JobDeduplication.job_id == job_id,
                JobDeduplication.indicator_hash == indicator_hash
            ).first() is not None
            return exists
        finally:
            session.close()
    
    def record_dedup(self, job_id: str, indicator_hash: str, finding_id: str):
        """Record deduplication entry"""
        session: Session = self.SessionLocal()
        try:
            from models import JobDeduplication
            dedup = JobDeduplication(
                job_id=job_id,
                indicator_hash=indicator_hash,
                finding_id=finding_id
            )
            session.add(dedup)
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create_audit_log(self, log_data: Dict):
        """Insert audit log entry"""
        session: Session = self.SessionLocal()
        try:
            from models import AuditLog
            log = AuditLog(**log_data)
            session.add(log)
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
```

**Tarea 2.2**: Elasticsearch Client

```python
# services/shared/es_client.py

from elasticsearch import Elasticsearch
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class ElasticsearchClient:
    def __init__(self, hosts: List[str]):
        self.client = Elasticsearch(hosts)
        self.findings_index = "findings"
        self.module_runs_index = "module_runs"
    
    def index_finding(self, finding_id: str, finding_data: Dict):
        """Index single finding"""
        try:
            self.client.index(
                index=self.findings_index,
                id=finding_id,
                body=finding_data,
                refresh=False
            )
        except Exception as e:
            logger.error(f"Error indexing finding: {e}")
            raise
    
    def bulk_index_findings(self, findings: List[Dict], chunk_size=1000):
        """Bulk index findings"""
        from elasticsearch.helpers import bulk
        try:
            actions = [
                {
                    "_index": self.findings_index,
                    "_id": f.get("finding_id"),
                    "_source": f
                }
                for f in findings
            ]
            success, failed = bulk(self.client, actions, chunk_size=chunk_size)
            logger.info(f"Bulk indexed: {success} success, {failed} failed")
            return success, failed
        except Exception as e:
            logger.error(f"Bulk indexing error: {e}")
            raise
    
    def search_findings(self, query: Dict, size: int = 100, offset: int = 0) -> Dict:
        """Search findings"""
        try:
            body = {
                "query": query,
                "from": offset,
                "size": size
            }
            results = self.client.search(index=self.findings_index, body=body)
            return {
                "total": results["hits"]["total"]["value"],
                "findings": [hit["_source"] for hit in results["hits"]["hits"]]
            }
        except Exception as e:
            logger.error(f"Search error: {e}")
            raise
    
    def search_findings_by_job(self, job_id: str, filters: Optional[Dict] = None) -> List[Dict]:
        """Search findings by job with optional filters"""
        query = {"bool": {"must": [{"term": {"job_id": job_id}}]}}
        
        if filters:
            if filters.get("type"):
                query["bool"]["must"].append({"terms": {"type": filters["type"]}})
            if filters.get("confidence_min"):
                query["bool"]["must"].append({
                    "range": {"confidence": {"gte": filters["confidence_min"]}}
                })
        
        results = self.search_findings(query)
        return results["findings"]
    
    def get_aggregations(self, job_id: str, aggregations: Dict) -> Dict:
        """Get aggregations"""
        try:
            body = {
                "query": {"term": {"job_id": job_id}},
                "size": 0,
                "aggs": aggregations
            }
            results = self.client.search(index=self.findings_index, body=body)
            return results.get("aggregations", {})
        except Exception as e:
            logger.error(f"Aggregation error: {e}")
            raise
    
    def health_check(self) -> bool:
        """Check health"""
        try:
            health = self.client.cluster.health()
            return health["status"] != "red"
        except:
            return False
```

**Tarea 2.3**: Neo4j Client

```python
# services/shared/neo4j_client.py

from neo4j import GraphDatabase
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def create_entity(self, name: str, entity_type: str, properties: Dict = None) -> str:
        """Create or merge Entity node"""
        with self.driver.session() as session:
            try:
                result = session.execute_write(
                    self._merge_entity,
                    name, entity_type, properties or {}
                )
                return result
            except Exception as e:
                logger.error(f"Error creating entity: {e}")
                raise
    
    @staticmethod
    def _merge_entity(tx, name: str, entity_type: str, properties: Dict):
        query = """
        MERGE (e:Entity {name: $name, type: $type})
        ON CREATE SET e.created_at = datetime()
        ON MATCH SET e.last_seen = datetime()
        SET e += $properties
        RETURN e.id
        """
        result = tx.run(query, name=name, type=entity_type, properties=properties)
        return result.single()[0]
    
    def link_entity_to_finding(self, entity_name: str, entity_type: str, finding_id: str, rel_type: str = "MENTIONED_IN", properties: Dict = None):
        """Create relationship between Entity and Finding"""
        with self.driver.session() as session:
            try:
                session.execute_write(
                    self._create_relationship,
                    entity_name, entity_type, finding_id, rel_type, properties or {}
                )
            except Exception as e:
                logger.error(f"Error creating relationship: {e}")
                raise
    
    @staticmethod
    def _create_relationship(tx, entity_name: str, entity_type: str, finding_id: str, rel_type: str, properties: Dict):
        query = f"""
        MATCH (e:Entity {{name: $entity_name, type: $entity_type}})
        MATCH (f:Finding {{finding_id: $finding_id}})
        MERGE (e)-[r:{rel_type}]->(f)
        ON CREATE SET r.created_at = datetime()
        SET r += $properties
        """
        tx.run(query, entity_name=entity_name, entity_type=entity_type, finding_id=finding_id, properties=properties)
    
    def get_shortest_path(self, start_entity: str, end_entity: str) -> List[Dict]:
        """Find shortest path"""
        with self.driver.session() as session:
            try:
                query = """
                MATCH p = shortestPath((a:Entity {name: $start})-[*]-(b:Entity {name: $end}))
                RETURN p LIMIT 1
                """
                result = session.run(query, start=start_entity, end=end_entity)
                return [record["p"] for record in result]
            except Exception as e:
                logger.error(f"Error getting shortest path: {e}")
                raise
    
    def health_check(self) -> bool:
        """Check Neo4j health"""
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            return True
        except:
            return False
```

**Tests para Fase 1-2**:
```bash
# Unit tests
pytest services/shared/tests/test_db_client.py
pytest services/shared/tests/test_es_client.py
pytest services/shared/tests/test_neo4j_client.py

# Integration tests
pytest services/shared/tests/test_integration.py
```

---

## 5. IMPLEMENTACIÓN FASE 3-4: API & WORKERS

### Fase 3: API Redesign (Semana 4-5)

**36 Endpoints** (FastAPI en `services/api/app/api/routes.py`):

```python
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict

app = FastAPI()

# ============================================================
# JOBS ENDPOINTS (6)
# ============================================================

@app.post("/api/v1/jobs")
def create_job(job_data: Dict):
    """Create new search job"""
    # Validar input
    # Crear en PostgreSQL
    # Enqueue en Celery
    # Retornar job_id + token WebSocket

@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str):
    """Get job status and results"""
    # Query PostgreSQL
    # Si status = completed: query ES + Neo4j
    # Retornar resultados

@app.get("/api/v1/jobs")
def list_jobs(skip: int = 0, limit: int = 10):
    """List all jobs"""
    # Query PostgreSQL con paginación

@app.delete("/api/v1/jobs/{job_id}")
def cancel_job(job_id: str):
    """Cancel running job"""
    # Revoke Celery task
    # Update job status

@app.post("/api/v1/jobs/{job_id}/retry")
def retry_job(job_id: str):
    """Retry failed job"""
    # Check if failed
    # Enqueue new task

@app.post("/api/v1/jobs/{job_id}/pause")
def pause_job(job_id: str):
    """Pause running job"""
    # Signal worker to pause

# ============================================================
# FINDINGS ENDPOINTS (10)
# ============================================================

@app.get("/api/v1/findings/search")
def search_findings(q: str, type: Optional[List[str]] = None, confidence_min: float = 0.0):
    """Full-text search findings"""
    # Build ES query
    # Apply filters
    # Return paginated results

@app.get("/api/v1/findings/{finding_id}")
def get_finding(finding_id: str):
    """Get single finding"""
    # Query ES

@app.post("/api/v1/findings/{finding_id}/tag")
def tag_finding(finding_id: str, tags: List[str]):
    """Add tags to finding"""
    # Update in ES + PostgreSQL

@app.post("/api/v1/findings/{finding_id}/verify")
def verify_finding(finding_id: str, user_id: str):
    """Mark finding as verified"""
    # Update in PostgreSQL
    # Update audit log

@app.get("/api/v1/findings")
def list_findings(job_id: str, skip: int = 0, limit: int = 100):
    """List findings for job"""
    # Query ES by job_id

# ... 5 more endpoint definitions

# ============================================================
# AGGREGATIONS ENDPOINTS (4)
# ============================================================

@app.get("/api/v1/findings/agg/by-type")
def agg_by_type(job_id: str):
    """Count findings by type"""
    # ES aggregation: terms on 'type'

@app.get("/api/v1/findings/agg/by-module")
def agg_by_module(job_id: str):
    """Count findings by module"""
    # ES aggregation: terms on 'module_name'

@app.get("/api/v1/findings/agg/timeline")
def agg_timeline(job_id: str, interval: str = "day"):
    """Timeline aggregation"""
    # ES aggregation: date_histogram on 'timestamp'

@app.get("/api/v1/findings/agg/confidence")
def agg_confidence(job_id: str, buckets: int = 10):
    """Confidence distribution"""
    # ES aggregation: histogram on 'confidence'

# ============================================================
# EXPORT ENDPOINTS (3)
# ============================================================

@app.post("/api/v1/jobs/{job_id}/export/json")
def export_json(job_id: str):
    """Export to JSON"""
    # Enqueue async task
    # Return task_id

@app.post("/api/v1/jobs/{job_id}/export/csv")
def export_csv(job_id: str):
    """Export to CSV"""
    # Enqueue async task

@app.post("/api/v1/jobs/{job_id}/export/pdf")
def export_pdf(job_id: str):
    """Export to PDF with graphs"""
    # Enqueue async task

# ============================================================
# GRAPH ENDPOINTS (4)
# ============================================================

@app.get("/api/v1/graph/entities")
def get_entities(job_id: str):
    """Get entity graph nodes"""
    # Query Neo4j: MATCH (e:Entity)-[r:FROM_JOB]->(j:Job {id})

@app.get("/api/v1/graph/relationships")
def get_relationships(job_id: str):
    """Get entity graph edges"""
    # Query Neo4j: relationships

@app.post("/api/v1/graph/shortest-path")
def shortest_path(start: str, end: str):
    """Shortest path between entities"""
    # Query Neo4j: shortestPath()

@app.post("/api/v1/graph/community-detect")
def community_detect(job_id: str):
    """Community detection"""
    # Query Neo4j: Louvain algorithm

# ============================================================
# ANALYTICS ENDPOINTS (3)
# ============================================================

@app.get("/api/v1/analytics/system")
def system_stats():
    """System statistics"""
    # Collect from all services

@app.get("/api/v1/analytics/modules")
def module_stats():
    """Module performance stats"""
    # Query module_runs table

@app.get("/api/v1/analytics/search-trends")
def search_trends():
    """Search trends"""
    # Query findings with time aggregation

# ============================================================
# CONFIG ENDPOINTS (3)
# ============================================================

@app.get("/api/v1/config/search")
def get_search_config():
    """Get search configuration options"""
    # Return available parameters

@app.post("/api/v1/config/search")
def save_search_config(config: Dict):
    """Save custom search configuration"""
    # Store in system_config table

@app.get("/api/v1/config/modules")
def get_modules_config():
    """Get modules registry"""
    # Return available modules

# ============================================================
# BATCH ENDPOINTS (2)
# ============================================================

@app.post("/api/v1/batch/jobs")
def create_batch_jobs(jobs_list: List[Dict]):
    """Create multiple jobs at once"""
    # Enqueue all

@app.get("/api/v1/batch/results/{batch_id}")
def get_batch_results(batch_id: str):
    """Get batch results"""
    # Collect all job results

# ============================================================
# ADMIN ENDPOINTS (1)
# ============================================================

@app.get("/api/v1/admin/health")
def health_check():
    """Health check all services"""
    # Check PG, ES, Neo4j, Redis
```

**WebSocket Real-time**:

```python
from fastapi import WebSocket
from typing import Set

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@app.websocket("/ws/jobs/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await manager.connect(websocket)
    try:
        # Subscribe to Redis Streams for job updates
        async for message in get_job_updates(job_id):
            await websocket.send_json(message)
    except Exception as e:
        manager.disconnect(websocket)
```

### Fase 4: Worker Optimization (Semana 5-6)

**Actualizar Coordinator** (`services/worker/tasks/coordinator.py`):

```python
from celery import Celery
from tasks.dynamic_orchestrator import DynamicModuleOrchestrator
from tasks.result_processor import ResultProcessor
from shared.db_client import PostgreSQLClient
from shared.es_client import ElasticsearchClient
from shared.neo4j_client import Neo4jClient

app = Celery(__name__)

@app.task(bind=True, name='search.dynamic', max_retries=3)
def execute_dynamic_search(self, job_id: str, search_params: Dict):
    """Main search task (v2.0)"""
    db = PostgreSQLClient(DATABASE_URL)
    es = ElasticsearchClient([ELASTICSEARCH_HOST])
    neo4j = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    try:
        # 1. Update job status
        job_status = db.get_job(job_id)
        job_status.update({"status": "processing"})
        
        # 2. Execute dynamic search
        orchestrator = DynamicModuleOrchestrator()
        results = orchestrator.execute(
            search_params,
            progress_callback=lambda p: publish_progress(job_id, p)
        )
        
        # 3. Process results
        processor = ResultProcessor()
        processed = processor.process(results)
        
        # 4. Persist to all systems
        for finding in processed['findings']:
            # PostgreSQL (atomic)
            finding_id = db.create_finding(finding)
            
            # Elasticsearch (async)
            es.index_finding(finding_id, finding)
            
            # Neo4j (async)
            for indicator in finding.get('extracted_indicators', []):
                entity_id = neo4j.create_entity(
                    indicator['value'],
                    indicator['type'],
                    {'job_id': job_id}
                )
                neo4j.link_entity_to_finding(
                    indicator['value'],
                    indicator['type'],
                    finding_id
                )
        
        # 5. Build correlations (post-search)
        for entity in neo4j.get_entities_for_job(job_id):
            correlations = find_entity_correlations(entity, neo4j)
            for corr in correlations:
                neo4j.create_relationship(entity, corr['entity'], corr)
        
        # 6. Update job complete
        db.update_job({
            "job_id": job_id,
            "status": "completed",
            "result": {
                "total_findings": len(processed['findings']),
                "modules_executed": len(results),
                "duration_seconds": time.time() - start_time
            }
        })
        
        # 7. Publish completion event
        publish_to_redis_stream(job_id, {
            "type": "job_completed",
            "total_findings": len(processed['findings'])
        })
        
    except TemporaryError as e:
        # Retry con backoff exponencial
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
    except PermanentError as e:
        # Send to DLQ
        db.update_job({
            "job_id": job_id,
            "status": "failed",
            "error": str(e)
        })
        send_to_dead_letter_queue(job_id, e)
    finally:
        neo4j.close()

def publish_progress(job_id: str, progress: Dict):
    """Publish progress to Redis Streams (real-time WebSocket)"""
    redis_client.xadd(
        f"job-updates:{job_id}",
        {"progress": progress}
    )
```

---

## 6. IMPLEMENTACIÓN FASE 5: FRONTEND

### Dashboard Components (Vue.js + D3.js)

**Estructura**:
```
services/api/app/static/
├─ js/
│  ├─ app.js                  (main Vue app)
│  ├─ components/
│  │  ├─ SearchForm.vue       (search input + filters)
│  │  ├─ ResultsTable.vue     (findings table)
│  │  ├─ Graph.vue            (D3.js network graph)
│  │  ├─ Timeline.vue         (Chart.js timeline)
│  │  ├─ Stats.vue            (statistics panel)
│  │  └─ Export.vue           (export buttons)
│  └─ utils/
│     ├─ api.js               (API client)
│     ├─ websocket.js         (WebSocket handler)
│     └─ formatters.js        (data formatting)
├─ css/
│  └─ style.css
└─ index.html
```

**Main App** (`services/api/app/static/js/app.js`):

```javascript
import Vue from 'vue'
import App from './App.vue'

Vue.config.productionTip = false

// Real-time updates
const ws = new WebSocket(`ws://${window.location.host}/ws/jobs/${jobId}`)

ws.onmessage = (event) => {
  const update = JSON.parse(event.data)
  
  if (update.type === 'finding_added') {
    store.commit('addFinding', update.data)
  } else if (update.type === 'job_completed') {
    store.commit('setJobComplete', update.data)
  }
}

new Vue({
  store,
  render: h => h(App)
}).$mount('#app')
```

**Graph Visualization** (D3.js):

```html
<template>
  <div id="graph-container"></div>
</template>

<script>
import * as d3 from 'd3'

export default {
  methods: {
    renderGraph(entities, relationships) {
      const svg = d3.select('#graph-container')
        .append('svg')
        .attr('width', 800)
        .attr('height', 600)
      
      const simulation = d3.forceSimulation(entities)
        .force('link', d3.forceLink(relationships).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(400, 300))
      
      const link = svg.selectAll('line')
        .data(relationships)
        .enter().append('line')
        .attr('stroke', '#999')
      
      const node = svg.selectAll('circle')
        .data(entities)
        .enter().append('circle')
        .attr('r', 8)
        .attr('fill', d => this.colorByType(d.type))
        .call(d3.drag()
          .on('start', dragstarted)
          .on('drag', dragged)
          .on('end', dragended))
      
      simulation.on('tick', () => {
        link
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y)
        
        node
          .attr('cx', d => d.x)
          .attr('cy', d => d.y)
      })
    }
  }
}
</script>
```

---

## 7. CHECKLISTS

### Pre-implementación

```
DOCUMENTACIÓN:
□ Equipo entiende arquitectura (ARCHITECTURE_REDESIGN.md)
□ Equipo entiende plan (este documento)
□ No hay dudas sobre stack tecnológico
□ ROI y timeline aprobados

RECURSOS:
□ 2-3 engineers asignados
□ DevOps disponible (50%)
□ QA disponible (30%)
□ Presupuesto aprobado

AMBIENTE:
□ Docker v2 stack creado
□ PostgreSQL 15+ disponible
□ Elasticsearch 8.10+ disponible
□ Neo4j 5+ disponible
□ Redis 7+ disponible
□ MinIO disponible

BACKUP:
□ PostgreSQL backup completado
□ Elasticsearch snapshot completado
□ Producción lista para rollback
```

### Fase 1-2: Database (Semana 2-3)

```
Fase 0:
□ Branch develop-v2-implementation creada
□ Backups completados
□ docker-compose.v2.yml actualizado
□ Connectivity a todos servicios verificada

Fase 1:
□ Schema PostgreSQL creado y testeado
□ Elasticsearch mappings creados
□ Neo4j constraints creados
□ MinIO buckets creados

Fase 2:
□ PostgreSQL Client implementado y testeado
□ Elasticsearch Client implementado y testeado
□ Neo4j Client implementado y testeado
□ Unit tests pasando (>80% coverage)
□ Integration tests pasando

Verification:
□ Queries de búsqueda en <200ms
□ Bulk indexing a ES funcionando
□ Neo4j queries funcionando
□ Deduplicación funcionando
```

### Fase 3-4: API & Workers (Semana 4-6)

```
Fase 3:
□ 36 endpoints implementados
□ OpenAPI docs generados
□ WebSocket conectando
□ Autenticación JWT funcionando
□ Paginación implementada
□ Filters implementados

Fase 4:
□ Coordinator.py actualizado
□ Dynamic orchestrator v2 funcionando
□ Result processor actualizado
□ Deduplicación 3-level funcionando
□ Metrics collection funcionando
□ Error handling + DLQ funcional

Integration Tests:
□ Búsqueda end-to-end funcionando
□ Datos persistiendo en PostgreSQL
□ Datos indexando en Elasticsearch
□ Entidades en Neo4j
□ WebSocket updates llegando
□ Performance baseline medido
```

### Fase 5: Frontend (Semana 6-7)

```
Dashboard:
□ Search form funcionando
□ Results table con paginación
□ Filters funcionales
□ D3.js graph renderizando
□ Timeline chart funcionando
□ Stats panel actualizado

Real-time:
□ WebSocket conectando
□ Datos actualizándose en vivo
□ Gráficos actualizándose
□ Notificaciones mostrando

Export:
□ Export a JSON funcionando
□ Export a CSV funcionando
□ Export a PDF funcionando
□ Signed URLs generadas
```

### Go-Live (Semana 7-8)

```
Testing:
□ Load testing completado (100+ concurrent users)
□ Failover testing completado
□ Backup/restore testing completado
□ Security testing completado
□ Performance benchmarks cumplidos

Data Migration:
□ Data migration script creado y testeado
□ Checksums verificados
□ Rollback procedure testeado
□ No data loss identificado

Deployment:
□ CI/CD pipeline funcional
□ Docker images creadas y pushed
□ Staging environment replicando producción
□ Runbooks creados
□ On-call rotación establecida

Monitoring:
□ Prometheus scrape targets configurados
□ Grafana dashboards creados
□ Alertas configuradas
□ ELK stack para logs funcional

Go Decision:
□ Todos checklists pasando
□ Leadership aprobó
□ Rollback plan listo
□ Team trained

GO/NO-GO: __ GO __ NO-GO
```

---

## MATRIZ DE REFERENCIA RÁPIDA

### Tecnologías

| Componente | Tecnología | Documentación |
|-----------|-----------|--------------|
| Base de datos transaccional | PostgreSQL 15 | Section 3 |
| Search + Analytics | Elasticsearch 8.10 | Section 3 |
| Graph database | Neo4j 5 | Section 3 |
| Object storage | MinIO | Task 1.4 |
| Message broker | Redis 7 | Throughout |
| API Framework | FastAPI | Section 5 |
| Task Queue | Celery | Section 5 |
| Frontend | Vue.js + D3.js | Section 6 |

### Endpoints por Feature

| Feature | Endpoints | Section |
|---------|-----------|---------|
| Job Management | 6 | Section 5 (Fase 3) |
| Findings | 10 | Section 5 (Fase 3) |
| Aggregations | 4 | Section 5 (Fase 3) |
| Export | 3 | Section 5 (Fase 3) |
| Graph Queries | 4 | Section 5 (Fase 3) |
| Analytics | 3 | Section 5 (Fase 3) |
| Config | 3 | Section 5 (Fase 3) |
| Batch | 2 | Section 5 (Fase 3) |
| Admin | 1 | Section 5 (Fase 3) |

### Cronograma

| Fase | Duración | Actividad |
|------|----------|-----------|
| 0 | 1 semana | Preparación |
| 1-2 | 2 semanas | Database + Clients |
| 3-4 | 2 semanas | API + Workers |
| 5 | 1 semana | Frontend |
| 6 | 1 semana | Cutover |
| **Total** | **6-8 semanas** | 2-3 engineers |

---

## ERRORES COMUNES A EVITAR

```
❌ NO hacer:
- Cambiar todas las tablas de una vez (hacer migración gradual)
- No hacer backup antes de cambios
- No monitorear durante implementación
- Olvidar indices en PostgreSQL
- No testear deduplicación
- Hacer rollback sin procedimiento
- Cambiar en producción sin staging
- No hacer load testing antes de go-live

✅ SÍ hacer:
- Implementación en branches separadas
- Backups antes de cada fase
- Testing exhaustivo
- Gradual rollout
- Monitoring continuo
- Procedure documentation
- Staging replica antes de go-live
- Load testing >= 100 concurrent users
```

---

## CONTACTO & ESCALATION

Si durante implementación encuentras:
- **Errores de schema**: Revisar Section 3 SQL
- **Errores de cliente**: Revisar código en Tarea 2.1-2.3
- **Errores de API**: Revisar Section 5
- **Problemas de performance**: Revisar indices en Section 3
- **Issues de Neo4j**: Revisar model en Section 3
- **WebSocket issues**: Revisar Section 5 WebSocket code

---

**Documento Final**: OSINT_v2.0_IMPLEMENTATION_GUIDE.md  
**Versión**: 1.0 FINAL  
**Estado**: ✅ LISTO PARA EJECUTAR  
**Próximo paso**: Iniciar Fase 0 (Preparación)

---

🚀 **¡A IMPLEMENTAR!** 🚀
