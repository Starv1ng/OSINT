import time
import json
import asyncio
import os
import logging
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from .celery_app import app
from .dynamic_orchestrator import DynamicModuleOrchestrator
from .modules.utils.result_processor import ResultProcessor
from .modules.utils.input_analyzer import InputAnalyzer
from shared.postgres_client import PostgreSQLClient
from shared.elasticsearch_client import ElasticsearchClient
from shared.neo4j_client import Neo4jClient
from config import config

logger = logging.getLogger(__name__)

_pg_client = None
_es_client = None
_neo4j_client = None

def get_pg_client():
    global _pg_client
    if _pg_client is None:
        _pg_client = PostgreSQLClient(config.database.url)
    return _pg_client

def get_es_client():
    global _es_client
    if _es_client is None:
        _es_client = ElasticsearchClient([config.elasticsearch.host])
    return _es_client

def get_neo4j_client():
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient(config.neo4j.uri, config.neo4j.auth)
    return _neo4j_client

dynamic_orchestrator = DynamicModuleOrchestrator(
    max_iterations=config.orchestrator.max_iterations,
    relevance_threshold=config.orchestrator.relevance_threshold,
    execution_mode=config.orchestrator.execution_mode,
    pg_client=get_pg_client()
)

@app.task(bind=True, name='process_osint_job')
def process_osint_job(self, job_id: str, search_data: dict):
    query = search_data['value']
    logger.info(f"Processing job: {job_id} - Query: {query}")
    
    try:
        input_analysis = InputAnalyzer.analyze(query)
        logger.info(f"Type: {input_analysis['input_type']} (conf: {input_analysis['confidence']:.2f})")
        
        update_job_status(job_id, "processing")
        
        search_data_enhanced = dict(search_data)
        search_data_enhanced['input_analysis'] = input_analysis
        search_data_enhanced['preferred_modules'] = input_analysis['primary_modules']
        
        results = asyncio.run(dynamic_orchestrator.execute_dynamic_search(job_id, search_data_enhanced))
        
        if results.get('findings'):
            findings_to_save = []
            for finding in results['findings']:
                finding_data = {
                    'job_id': job_id,
                    'module_name': finding.get('module', 'unknown'),
                    'type': finding.get('type', 'general'),
                    'value': finding.get('value', ''),
                    'normalized_value': finding.get('normalized_value', finding.get('value', '')),
                    'confidence': finding.get('confidence', 0.5),
                    'relevance_score': finding.get('relevance_score', 0.5),
                    'source_url': finding.get('source_url'),
                    'raw_text': finding.get('raw_text'),
                    'metadata': finding.get('metadata', {})
                }
                
                finding_hash = get_pg_client().compute_finding_hash(finding_data)
                if not get_pg_client().check_dedup_exists(job_id, finding_hash):
                    try:
                        finding_id = get_pg_client().create_finding(finding_data)
                        get_pg_client().record_dedup(job_id, finding_hash, finding_id)
                        
                        finding_data['finding_id'] = finding_id
                        findings_to_save.append(finding_data)
                        
                        if finding.get('extracted_indicators'):
                            for indicator in finding['extracted_indicators']:
                                get_pg_client().create_indicator({
                                    'type': indicator.get('type'),
                                    'value': indicator.get('value'),
                                    'normalized_value': indicator.get('normalized_value', indicator.get('value')),
                                    'source_finding_id': finding_id,
                                    'confidence': indicator.get('confidence', 0.5)
                                })
                    except Exception as finding_error:
                        logger.error(f"Error processing finding {finding.get('value')}: {finding_error}")
            
            if findings_to_save:
                try:
                    success, errors = get_es_client().bulk_index_findings(findings_to_save)
                    logger.info(f"Indexed {success} findings, {errors} errors")
                except Exception as index_error:
                    logger.error(f"Error bulk indexing findings: {index_error}")
            
            processed = ResultProcessor.process_findings(
                results['findings'],
                query=query,
                context=input_analysis['input_type']
            )
            results['processed'] = processed
            
            logger.info(f"Saved {len(findings_to_save)} findings, {len(processed['extracted_indicators'].get('emails', []))} emails")
        
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
            logger.info(f"Job {job_id} status updated to {status}" + (f" (progress: {progress}%)" if progress else ""))
    except Exception as e:
        logger.error(f"Error updating job status: {e}")

def save_job_results(job_id: str, results: dict):
    try:
        with get_pg_client().get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE jobs SET result = %s, updated_at = NOW() WHERE job_id = %s",
                (json.dumps(results), job_id)
            )
            # Context manager commits automatically
        logger.info(f"Results saved for {job_id}")
    except Exception as e:
        logger.error(f"Error saving results: {e}")