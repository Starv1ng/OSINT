import os
import hashlib
import logging
from datetime import datetime
from elasticsearch import Elasticsearch, helpers
from config import config

logger = logging.getLogger(__name__)

# Obtener valores de configuración centralizada
ES_URL = config.elasticsearch.host
FINDINGS_INDEX = config.elasticsearch.findings_index
MODULE_RUNS_INDEX = config.elasticsearch.module_runs_index

# Mapeo mínimo para el índice de hallazgos
FINDINGS_MAPPING = {
    "mappings": {
        "properties": {
            "finding_id": {"type": "keyword"},
            "job_id": {"type": "keyword"},
            "module_run_id": {"type": "keyword"},
            "module_name": {"type": "keyword"},
            "type": {"type": "keyword"},
            "value": {"type": "text", "fields": {"raw": {"type": "keyword"}}},
            "normalized_value": {"type": "keyword"},
            "confidence": {"type": "float"},
            "metadata": {"type": "object", "enabled": True},
            "created_at": {"type": "date"},
            "text": {"type": "text"}
        }
    }
}


def _get_client():
    # Crear cliente de Elasticsearch; en modo single-node sin seguridad funcionará
    return Elasticsearch([ES_URL])


def _ensure_index(client):
    try:
        if not client.indices.exists(index=FINDINGS_INDEX):
            client.indices.create(index=FINDINGS_INDEX, body=FINDINGS_MAPPING)
    except Exception as e:
        logger.debug(f"es_client: no se pudo asegurar el índice {FINDINGS_INDEX}: {e}")


def _normalize_value(val: str) -> str:
    if not val:
        return ""
    try:
        return val.strip().lower()
    except Exception:
        return val


def _doc_id(job_id: str, finding: dict) -> str:
    # Identificador determinista para indexado idempotente
    ftype = finding.get('type', '')
    val = finding.get('value', '')
    norm = _normalize_value(val)
    raw = f"{job_id}|{ftype}|{norm}"
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


def index_findings(job_id: str, findings: list) -> dict:
    """Indexación masiva de hallazgos en Elasticsearch. Devuelve la respuesta del API bulk o dict vacío en caso de error."""
    if not findings:
        return {}

    client = _get_client()
    try:
        _ensure_index(client)
    except Exception:
        pass

    actions = []
    now = datetime.utcnow().isoformat()
    for f in findings:
        try:
            fid = _doc_id(job_id, f)
            doc = {
                "finding_id": fid,
                "job_id": job_id,
                "module_run_id": f.get('module_run_id'),
                "module_name": f.get('module', f.get('module_name')),
                "type": f.get('type'),
                "value": f.get('value'),
                "normalized_value": _normalize_value(f.get('value')),
                "confidence": f.get('confidence'),
                "metadata": f.get('metadata', {}),
                "created_at": f.get('created_at', now),
                "text": f.get('context') or f.get('text') or ''
            }

            actions.append({
                "_op_type": "index",
                "_index": FINDINGS_INDEX,
                "_id": fid,
                "_source": doc
            })
        except Exception as e:
            logger.debug(f"es_client: skipping finding due to error: {e}")

    if not actions:
        return {}

    try:
        success, errors = helpers.bulk(client, actions, raise_on_error=False)
        logger.info(f"es_client: indexed {success} findings for job {job_id}")
        return {"success": success, "errors": errors}
    except Exception as e:
        logger.error(f"es_client: bulk index failed: {e}")
        return {}


def _ensure_module_runs_index(client):
    mapping = {
        "mappings": {
            "properties": {
                "module_run_id": {"type": "keyword"},
                "job_id": {"type": "keyword"},
                "module_name": {"type": "keyword"},
                "status": {"type": "keyword"},
                "started_at": {"type": "date"},
                "finished_at": {"type": "date"},
                "raw_result": {"type": "object", "enabled": True},
                "raw_html": {"type": "text"}
            }
        }
    }
    try:
        if not client.indices.exists(index=MODULE_RUNS_INDEX):
            client.indices.create(index=MODULE_RUNS_INDEX, body=mapping)
    except Exception as e:
        logger.debug(f"es_client: could not ensure index {MODULE_RUNS_INDEX}: {e}")


def index_module_run(job_id: str, module_name: str, module_result: dict) -> str:
    """Index a module_run document and return module_run_id."""
    client = _get_client()
    try:
        _ensure_module_runs_index(client)
    except Exception:
        pass

    started = module_result.get('started_at') or module_result.get('metadata', {}).get('started_at')
    finished = module_result.get('finished_at') or module_result.get('metadata', {}).get('finished_at')

    # Create deterministic id (job + module)
    base = f"{job_id}|{module_name}"
    module_run_id = hashlib.sha1(base.encode('utf-8')).hexdigest()

    doc = {
        'module_run_id': module_run_id,
        'job_id': job_id,
        'module_name': module_name,
        'status': module_result.get('status', 'completed'),
        'started_at': started,
        'finished_at': finished,
        'raw_result': module_result,
        'raw_html': module_result.get('raw_html') or module_result.get('html') or module_result.get('content')
    }

    try:
        client.index(index=MODULE_RUNS_INDEX, id=module_run_id, document=doc)
        logger.info(f"es_client: indexed module_run {module_run_id} for job {job_id} module {module_name}")
    except Exception as e:
        logger.error(f"es_client: failed indexing module_run for {module_name}: {e}")

    return module_run_id
