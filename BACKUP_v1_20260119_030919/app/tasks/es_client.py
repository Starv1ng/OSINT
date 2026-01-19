import os
import logging
from elasticsearch import Elasticsearch

logger = logging.getLogger(__name__)

ES_URL = os.environ.get('ELASTIC_URL', 'http://elasticsearch:9200')
FINDINGS_INDEX = os.environ.get('ELASTIC_FINDINGS_INDEX', 'findings')
MODULE_RUNS_INDEX = os.environ.get('ELASTIC_MODULE_RUNS_INDEX', 'module_runs')


def _get_client():
    try:
        return Elasticsearch([ES_URL])
    except Exception as e:
        logger.debug(f"es_client(api): could not create client: {e}")
        return None


def get_findings(job_id: str, size: int = 100, from_: int = 0):
    client = _get_client()
    if not client:
        return []
    try:
        body = {
            "query": {"term": {"job_id": job_id}},
            "sort": [{"created_at": {"order": "asc"}}],
            "from": from_,
            "size": size
        }
        res = client.search(index=FINDINGS_INDEX, body=body)
        hits = res.get('hits', {}).get('hits', [])
        return [h.get('_source') for h in hits]
    except Exception as e:
        logger.debug(f"es_client(api): search failed: {e}")
        return []


def get_module_runs(job_id: str):
    client = _get_client()
    if not client:
        return []
    try:
        body = {
            "query": {"term": {"job_id": job_id}},
            "sort": [{"started_at": {"order": "asc"}}],
            "size": 100
        }
        res = client.search(index=MODULE_RUNS_INDEX, body=body)
        hits = res.get('hits', {}).get('hits', [])
        return [h.get('_source') for h in hits]
    except Exception as e:
        logger.debug(f"es_client(api): module_runs search failed: {e}")
        return []
