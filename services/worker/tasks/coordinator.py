import json
import asyncio
import os
import logging
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from .celery_app import app
from .dynamic_orchestrator import DynamicModuleOrchestrator
from .modules.utils.input_analyzer import InputAnalyzer
from shared.postgres_client import PostgreSQLClient
from shared.elasticsearch_client import ElasticsearchClient
from shared.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

# Configuration from environment variables
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://osint:osint@postgres:5432/osint')
ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST', 'http://elasticsearch:9200')
ELASTICSEARCH_FINDINGS_INDEX = os.getenv('ELASTICSEARCH_FINDINGS_INDEX', 'osint-findings')
ELASTICSEARCH_MODULE_RUNS_INDEX = os.getenv('ELASTICSEARCH_MODULE_RUNS_INDEX', 'osint-module-runs')
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://neo4j:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'osint')
MAX_ITERATIONS = int(os.getenv('MAX_ITERATIONS', 5))
RELEVANCE_THRESHOLD = float(os.getenv('RELEVANCE_THRESHOLD', 0.5))
EXECUTION_MODE = os.getenv('EXECUTION_MODE', 'normal')

_pg_client = None
_es_client = None
_neo4j_client = None


def _json_default(obj):
    """Best-effort serializer to keep job result persistence robust."""
    try:
        return str(obj)
    except Exception:
        return "<non-serializable>"


def get_pg_client():
    global _pg_client
    if _pg_client is None:
        _pg_client = PostgreSQLClient(DATABASE_URL)
    return _pg_client

def get_es_client():
    global _es_client
    if _es_client is None:
        _es_client = ElasticsearchClient(
            [ELASTICSEARCH_HOST],
            findings_index=ELASTICSEARCH_FINDINGS_INDEX,
            module_runs_index=ELASTICSEARCH_MODULE_RUNS_INDEX
        )
    return _es_client

def get_neo4j_client():
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient(NEO4J_URI, (NEO4J_USER, NEO4J_PASSWORD))
    return _neo4j_client

_dynamic_orchestrator = None

def get_dynamic_orchestrator():
    global _dynamic_orchestrator
    if _dynamic_orchestrator is None:
        _dynamic_orchestrator = DynamicModuleOrchestrator(
            max_iterations=MAX_ITERATIONS,
            relevance_threshold=RELEVANCE_THRESHOLD,
            execution_mode=EXECUTION_MODE,
            pg_client=get_pg_client()
        )
    return _dynamic_orchestrator

@app.task(bind=True, name='process_osint_job')
def process_osint_job(self, job_id: str, search_data: dict):
    dynamic_orchestrator = get_dynamic_orchestrator()
    query = search_data.get('value')
    if not query:
        raise ValueError("search_data must include a non-empty 'value'")
    logger.info(f"Processing job: {job_id} - Query: {query}")
    
    try:
        input_analysis = InputAnalyzer.analyze(query)
        logger.info(f"Type: {input_analysis['input_type']} (conf: {input_analysis['confidence']:.2f})")
        
        update_job_status(job_id, "processing")
        
        search_data_enhanced = dict(search_data)
        search_data_enhanced['input_analysis'] = input_analysis
        
        # Check if this is a custom/advanced search with user-selected modules
        selected_modules = search_data.get('selected_modules') or []
        if search_data.get('custom_search') and selected_modules:
            logger.info(f"Custom search with {len(selected_modules)} selected modules")
            search_data_enhanced['preferred_modules'] = selected_modules
            search_data_enhanced['custom_search'] = True
        else:
            # Use automatic module selection based on input type
            search_data_enhanced['preferred_modules'] = input_analysis['primary_modules']
        
        results = asyncio.run(dynamic_orchestrator.execute_dynamic_search(job_id, search_data_enhanced))

        
        if results.get('findings'):
            findings_to_save = []
            for finding in results['findings']:
                # Los findings ya vienen normalizados de dynamic_orchestrator
                finding_data = {
                    'job_id': job_id,
                    'module_name': finding.get('module_name', 'unknown'),
                    'type': finding.get('type', 'general'),
                    'value': finding.get('value', ''),
                    'normalized_value': finding.get('value', ''),  # Ya normalizados
                    'confidence': float(finding.get('confidence', 0.5)),
                    'relevance_score': float(finding.get('relevance_score', 0.5)),
                    'source_url': finding.get('source_url'),
                    'raw_text': finding.get('raw_text'),
                    'metadata': finding.get('metadata', {})
                }
                
                # Solo procesar si tiene un value válido (post-normalización)
                if not finding_data['value']:
                    logger.debug(f"Skipping finding without value: {finding}")
                    continue
                
                pg_client = get_pg_client()
                finding_hash = pg_client.compute_finding_hash(finding_data)
                if not pg_client.check_dedup_exists(job_id, finding_hash):
                    try:
                        finding_id = pg_client.create_finding(finding_data)
                        pg_client.record_dedup(job_id, finding_hash, finding_id)
                        
                        finding_data['finding_id'] = finding_id
                        findings_to_save.append(finding_data)
                        
                        # Guardar indicadores extraídos si existen
                        if finding.get('extracted_indicators'):
                            for indicator in finding['extracted_indicators']:
                                pg_client.create_indicator({
                                    'type': indicator.get('type'),
                                    'value': indicator.get('value'),
                                    'normalized_value': indicator.get('value'),
                                    'source_finding_id': finding_id,
                                    'confidence': float(indicator.get('confidence', 0.5))
                                })
                    except Exception as finding_error:
                        logger.error(f"Error processing finding {finding.get('value')}: {finding_error}")
            
            if findings_to_save:
                try:
                    success, errors = get_es_client().bulk_index_findings(findings_to_save)
                    logger.info(f"Saved {success} findings to DB, {errors} errors")
                except Exception as index_error:
                    logger.error(f"Error saving findings to DB: {index_error}")
            
            # Ya procesados en dynamic_orchestrator, pero incluir en resultado final
            logger.info(f"Total findings after dedup: {len(findings_to_save)}")
        
        save_job_results(job_id, results)
        update_job_status(job_id, "completed")
        
        logger.info(f"Job {job_id} completed: {len(results.get('findings', []))} findings")
        
        return {
            "job_id": job_id,
            "status": "completed",
            "input_type": input_analysis['input_type'],
            "findings_count": len(results.get('findings', [])),
            "processed_count": len(results.get('processed', {}).get('processed_findings', [])) if 'processed' in results else 0
        }
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        update_job_status(job_id, "failed")
        
        error_results = {
            "search_query": query,
            "search_type": search_data.get('input_type', 'unknown'),
            "findings": [],
            "error": str(e),
            "summary": {
                "total_findings": 0,
                "error": True,
                "error_message": str(e)
            }
        }
        save_job_results(job_id, error_results)
        
        return {
            "job_id": job_id,
            "status": "failed",
            "error": str(e)
        }


def update_job_status(job_id: str, status: str, progress: int = None):
    try:
        with get_pg_client().get_connection() as conn:
            cur = conn.cursor()
            if progress is not None:
                cur.execute(
                    "UPDATE jobs SET status = %s, progress = %s, updated_at = NOW() WHERE job_id = %s",
                    (status, progress, job_id)
                )
            else:
                cur.execute(
                    "UPDATE jobs SET status = %s, updated_at = NOW() WHERE job_id = %s",
                    (status, job_id)
                )
            progress_note = f" (progress: {progress}%)" if progress is not None else ""
            logger.info(f"Job {job_id} status updated to {status}{progress_note}")
    except Exception as e:
        logger.error(f"Error updating job status: {e}")

def save_job_results(job_id: str, results: dict):
    try:
        with get_pg_client().get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE jobs SET result = %s, updated_at = NOW() WHERE job_id = %s",
                (json.dumps(results, default=_json_default), job_id)
            )
            # Context manager commits automatically
        logger.info(f"Results saved for {job_id}")
    except Exception as e:
        logger.error(f"Error saving results: {e}")