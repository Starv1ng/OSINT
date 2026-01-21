# OSINT Intelligence Platform - AI Agent Instructions

## Architecture Overview

This is a **distributed OSINT (Open Source Intelligence) platform** with microservices architecture:

- **API Service** (`services/api/`): FastAPI gateway exposing REST endpoints and HTML templates
- **Worker Service** (`services/worker/`): Celery workers executing OSINT modules asynchronously
- **Data Stack**: PostgreSQL (jobs), Redis (Celery broker), Elasticsearch (findings), MinIO (storage), Neo4j (graph)

**Data Flow**: API → Redis queue → Worker (Celery task) → OSINT modules → Elasticsearch + PostgreSQL

## Key Architectural Patterns

### 1. Dynamic Module Orchestration
Search execution adapts based on **input type analysis**:

```python
# services/worker/tasks/coordinator.py - Main entry point
from .modules.utils.input_analyzer import InputAnalyzer

input_analysis = InputAnalyzer.analyze(query)  # Detects: email, username, domain, person, etc.
# Routes to appropriate modules based on type confidence
```

Two orchestrators exist:
- `ModuleOrchestrator` (static): Runs predefined module sets per input type
- `DynamicModuleOrchestrator` (iterative): Executes modules, extracts indicators, runs new modules on findings (up to `max_iterations`)

### 2. Module System (BaseSearcher Pattern)
All OSINT modules inherit from `BaseSearcher` (`services/worker/tasks/modules/base/base_searcher.py`):

```python
class TwitterSearcher(BaseSearcher):
    def search(self, query: str, search_type: str, options: Dict) -> Dict:
        # Returns: {"module": "twitter", "findings": [...], "success": bool}
    
    def get_supported_types(self) -> List[str]:
        return ["person", "username"]
```

**Module categories**:
- **MPG (Multi-Purpose Gatherers)**: `search`, `webspider` - collect raw HTML/content
- **MEI (Metadata Extractors)**: `mei_email`, `mei_phone`, `mei_username`, `mei_image` - extract indicators from raw content
- **Specialized**: `twitter`, `linkedin`, `github`, `dns_whois`, `breach`, etc.

### 3. Incremental Persistence
Findings index to Elasticsearch **during execution** (not only at end):

```python
# services/worker/tasks/es_client.py
index_findings(job_id, findings)  # Called per module run
```

Query results via:
- **PostgreSQL** `jobs` table: job status, inline results (JSONB `result` column)
- **Elasticsearch** `findings` index: detailed findings, searchable by job_id

### 4. Result Processing Pipeline
Three-stage post-processing (`services/worker/tasks/modules/utils/`):

1. **InputAnalyzer**: Detect input type (email, username, domain, etc.) → route to relevant modules
2. **ResultFilter**: Remove noise (generic domains, template text, low-confidence items)
3. **ResultProcessor**: Score findings, extract indicators (emails/phones/usernames), deduplicate

## Critical Developer Workflows

### Running the Stack
```powershell
# Start all services (Postgres, Redis, Elasticsearch, API, Worker)
docker-compose up -d

# Rebuild specific service after code changes
docker-compose up -d --build api
docker-compose up -d --build worker

# View worker logs (see Celery task execution)
docker-compose logs -f worker
```

### Testing Workflow
```powershell
# Verify environment dependencies
python verify_env.py

# Test intelligent system integration
python verify_intelligent_system.py

# Test dynamic search (in worker container)
docker-compose exec worker python test_dynamic_search.py
```

### Creating New OSINT Modules
1. Inherit from `BaseSearcher` in `services/worker/tasks/modules/`
2. Implement `search()`, `get_supported_types()`, `get_priority()`
3. Register in orchestrator's `self.modules` dict (`orchestrator.py`, `dynamic_orchestrator.py`)
4. Add to `INDICATOR_MODULE_MAPPING` in `services/worker/config/dynamic_search_config.py`

### Debugging Jobs
```python
# API creates job → Worker processes → Check status
# 1. Check PostgreSQL job status
GET /api/v1/jobs/{job_id}

# 2. Check Elasticsearch findings
from tasks.es_client import get_findings
findings = get_findings(job_id)

# 3. View Celery task logs
docker-compose logs worker | grep {job_id}
```

## Project-Specific Conventions

### Import Paths
Worker tasks import from `tasks.` root (see `services/worker/Dockerfile` CMD):
```python
from tasks.celery_app import app  # NOT from .celery_app
from tasks.coordinator import process_osint_job
```

### Celery Task Naming
Tasks **must** use explicit names for cross-service communication:
```python
@app.task(bind=True, name='process_osint_job')  # API sends to this name
def process_osint_job(self, job_id, search_data):
    ...
```

### Environment Configuration
- API service: `envs/api.env` (DATABASE_URL, CELERY_BROKER, MINIO, SECRET_KEY)
- Worker service: `envs/worker.env` (same DB/broker, no SECRET_KEY needed)
- Dynamic search modes: Set `EXECUTION_MODE=aggressive|normal|conservative` or use config presets

### Authentication (Development Mode)
Auth is **bypassed** in `services/api/app/api/auth.py`:
```python
def get_current_user(token: Optional[str] = Depends(oauth2_scheme)):
    return {"username": "dev", "role": "admin"}  # Always succeeds
```

### Database Schema
Single `jobs` table (`infra/init_db.sql`):
- `job_id` (TEXT PRIMARY KEY), `status` (accepted/processing/completed/failed)
- `result` (JSONB) - stores inline results, supplemented by Elasticsearch

## Key Files Reference

- `services/worker/tasks/coordinator.py` - Celery task entry point, calls orchestrators
- `services/worker/tasks/dynamic_orchestrator.py` - Iterative search with indicator extraction
- `services/worker/tasks/modules/utils/input_analyzer.py` - Input type detection logic
- `services/api/app/api/routes.py` - REST endpoints (`/ingest/name`, `/jobs/{id}`)
- `services/api/app/tasks/enqueue.py` - Sends Celery tasks from API to worker
- `docker-compose.yml` - Service definitions, ports, volumes

## When Working On...

**New endpoints**: Add to `services/api/app/api/routes.py`, use `Depends(get_current_user)` for auth bypass

**New Celery tasks**: Define in `services/worker/tasks/`, register in `celery_app.py` imports

**UI changes**: Edit Jinja2 templates in `services/api/app/templates/`, static assets in `static/`

**Search tuning**: Adjust `services/worker/config/dynamic_search_config.py` (iterations, thresholds, module mappings)

**Database migrations**: Use Alembic (installed) or modify `infra/init_db.sql` and recreate Postgres volume
