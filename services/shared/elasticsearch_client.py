"""
Elasticsearch Client for OSINT v2.0
Handles search indexing, full-text search, and aggregations
"""

from elasticsearch import Elasticsearch, helpers
from typing import List, Dict, Optional, Any, Tuple
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """Elasticsearch client for OSINT findings and metrics"""
    
    # Findings mapping
    FINDINGS_MAPPING = {
        "mappings": {
            "properties": {
                "finding_id": {"type": "keyword"},
                "job_id": {"type": "keyword"},
                "module_run_id": {"type": "keyword"},
                "module_name": {"type": "keyword"},
                "type": {"type": "keyword"},
                "value": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                },
                "normalized_value": {"type": "keyword"},
                "confidence": {"type": "float"},
                "relevance_score": {"type": "float"},
                "verified": {"type": "boolean"},
                "iteration": {"type": "integer"},
                "source_url": {"type": "keyword"},
                "raw_text": {
                    "type": "text",
                    "analyzer": "standard"
                },
                "metadata": {"type": "object", "enabled": True},
                "tags": {"type": "keyword"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "extracted_indicators": {
                    "type": "nested",
                    "properties": {
                        "type": {"type": "keyword"},
                        "value": {"type": "keyword"},
                        "confidence": {"type": "float"}
                    }
                }
            }
        },
        "settings": {
            "number_of_shards": 3,
            "number_of_replicas": 1,
            "index.codec": "best_compression",
            "index.refresh_interval": "30s",
            "analysis": {
                "analyzer": {
                    "osint_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "asciifolding"]
                    }
                }
            }
        }
    }
    
    # Module runs mapping
    MODULE_RUNS_MAPPING = {
        "mappings": {
            "properties": {
                "module_run_id": {"type": "keyword"},
                "job_id": {"type": "keyword"},
                "module_name": {"type": "keyword"},
                "status": {"type": "keyword"},
                "started_at": {"type": "date"},
                "finished_at": {"type": "date"},
                "duration_ms": {"type": "integer"},
                "findings_count": {"type": "integer"},
                "errors": {"type": "text"},
                "created_at": {"type": "date"}
            }
        },
        "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 1
        }
    }
    
    def __init__(self, hosts: List[str], timeout: int = 30):
        """
        Initialize Elasticsearch client
        
        Args:
            hosts: List of Elasticsearch hosts
            timeout: Request timeout in seconds
        """
        self.es = Elasticsearch(hosts, timeout=timeout)
        self.logger = logging.getLogger(__name__)
        self.findings_index = "findings-v2"
        self.module_runs_index = "module-runs-v2"
    
    # ============================================================
    # INDEX MANAGEMENT
    # ============================================================
    
    def create_indices(self):
        """Create all required indices with mappings"""
        # Create findings index
        if not self.es.indices.exists(index=self.findings_index):
            self.es.indices.create(
                index=self.findings_index,
                body=self.FINDINGS_MAPPING
            )
            self.logger.info(f"Created index: {self.findings_index}")
        
        # Create module runs index
        if not self.es.indices.exists(index=self.module_runs_index):
            self.es.indices.create(
                index=self.module_runs_index,
                body=self.MODULE_RUNS_MAPPING
            )
            self.logger.info(f"Created index: {self.module_runs_index}")
    
    def delete_index(self, index_name: str):
        """Delete an index"""
        if self.es.indices.exists(index=index_name):
            self.es.indices.delete(index=index_name)
            self.logger.info(f"Deleted index: {index_name}")
    
    # ============================================================
    # FINDINGS OPERATIONS
    # ============================================================
    
    def index_finding(self, finding_id: str, finding_data: Dict) -> bool:
        """
        Index a single finding
        
        Args:
            finding_id: UUID of finding
            finding_data: Finding dictionary with all fields
        
        Returns:
            Success boolean
        """
        try:
            # Ensure dates are formatted correctly
            if 'created_at' in finding_data and isinstance(finding_data['created_at'], datetime):
                finding_data['created_at'] = finding_data['created_at'].isoformat()
            if 'updated_at' in finding_data and isinstance(finding_data['updated_at'], datetime):
                finding_data['updated_at'] = finding_data['updated_at'].isoformat()
            
            self.es.index(
                index=self.findings_index,
                id=finding_id,
                document=finding_data,
                refresh=False  # Async refresh for performance
            )
            return True
        except Exception as e:
            self.logger.error(f"Error indexing finding {finding_id}: {e}")
            return False
    
    def bulk_index_findings(self, findings: List[Dict], chunk_size: int = 500) -> Tuple[int, int]:
        """
        Bulk index multiple findings
        
        Args:
            findings: List of finding dictionaries with finding_id included
            chunk_size: Number of documents per bulk request
        
        Returns:
            Tuple of (success_count, error_count)
        """
        if not findings:
            return (0, 0)
        
        actions = []
        for finding in findings:
            finding_id = finding.get('finding_id')
            if not finding_id:
                continue
            
            # Format dates
            if 'created_at' in finding and isinstance(finding['created_at'], datetime):
                finding['created_at'] = finding['created_at'].isoformat()
            if 'updated_at' in finding and isinstance(finding['updated_at'], datetime):
                finding['updated_at'] = finding['updated_at'].isoformat()
            
            actions.append({
                "_index": self.findings_index,
                "_id": finding_id,
                "_source": finding
            })
        
        try:
            success, errors = helpers.bulk(
                self.es,
                actions,
                chunk_size=chunk_size,
                raise_on_error=False,
                refresh=False
            )
            
            if errors:
                self.logger.warning(f"Bulk index had {len(errors)} errors")
            
            return (success, len(errors))
        except Exception as e:
            self.logger.error(f"Bulk index error: {e}")
            return (0, len(findings))
    
    def get_finding(self, finding_id: str) -> Optional[Dict]:
        """Get single finding by ID"""
        try:
            result = self.es.get(index=self.findings_index, id=finding_id)
            return result['_source']
        except Exception as e:
            self.logger.error(f"Error getting finding {finding_id}: {e}")
            return None
    
    def update_finding(self, finding_id: str, updates: Dict) -> bool:
        """Update finding fields"""
        try:
            self.es.update(
                index=self.findings_index,
                id=finding_id,
                body={"doc": updates}
            )
            return True
        except Exception as e:
            self.logger.error(f"Error updating finding {finding_id}: {e}")
            return False
    
    # ============================================================
    # SEARCH OPERATIONS
    # ============================================================
    
    def search_findings(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict] = None,
        size: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict:
        """
        Search findings with full-text query and filters
        
        Args:
            query: Full-text search query
            filters: Dictionary of filters (job_id, type, min_confidence, etc.)
            size: Maximum results
            offset: Results offset for pagination
            sort_by: Field to sort by
            sort_order: Sort order (asc/desc)
        
        Returns:
            Dictionary with hits and total count
        """
        body = {
            "size": size,
            "from": offset,
            "sort": [{sort_by: {"order": sort_order}}]
        }
        
        # Build query
        must_clauses = []
        filter_clauses = []
        
        # Full-text search
        if query:
            must_clauses.append({
                "multi_match": {
                    "query": query,
                    "fields": ["value^2", "raw_text", "normalized_value"],
                    "type": "best_fields",
                    "operator": "or"
                }
            })
        
        # Filters
        if filters:
            if 'job_id' in filters:
                filter_clauses.append({"term": {"job_id": filters['job_id']}})
            if 'type' in filters:
                filter_clauses.append({"term": {"type": filters['type']}})
            if 'module_name' in filters:
                filter_clauses.append({"term": {"module_name": filters['module_name']}})
            if 'min_confidence' in filters:
                filter_clauses.append({"range": {"confidence": {"gte": filters['min_confidence']}}})
            if 'verified' in filters:
                filter_clauses.append({"term": {"verified": filters['verified']}})
            if 'tags' in filters:
                filter_clauses.append({"terms": {"tags": filters['tags']}})
        
        # Combine clauses
        if must_clauses or filter_clauses:
            body["query"] = {
                "bool": {
                    "must": must_clauses if must_clauses else [{"match_all": {}}],
                    "filter": filter_clauses
                }
            }
        else:
            body["query"] = {"match_all": {}}
        
        try:
            result = self.es.search(index=self.findings_index, body=body)
            
            return {
                "total": result['hits']['total']['value'],
                "hits": [hit['_source'] for hit in result['hits']['hits']],
                "max_score": result['hits'].get('max_score'),
                "took_ms": result['took']
            }
        except Exception as e:
            self.logger.error(f"Search error: {e}")
            return {"total": 0, "hits": [], "error": str(e)}
    
    def search_findings_by_job(self, job_id: str, filters: Optional[Dict] = None) -> List[Dict]:
        """Convenience method to search findings for a specific job"""
        filters = filters or {}
        filters['job_id'] = job_id
        result = self.search_findings(filters=filters, size=10000)
        return result['hits']
    
    # ============================================================
    # AGGREGATIONS
    # ============================================================
    
    def get_aggregations(self, job_id: str, agg_fields: List[str]) -> Dict:
        """
        Get aggregations for a job
        
        Args:
            job_id: Job identifier
            agg_fields: List of fields to aggregate (type, module_name, etc.)
        
        Returns:
            Dictionary with aggregation results
        """
        body = {
            "size": 0,
            "query": {"term": {"job_id": job_id}},
            "aggs": {}
        }
        
        # Build aggregations
        for field in agg_fields:
            body["aggs"][f"{field}_counts"] = {
                "terms": {
                    "field": field,
                    "size": 100
                }
            }
        
        # Add statistics aggregations
        body["aggs"]["confidence_stats"] = {
            "stats": {"field": "confidence"}
        }
        body["aggs"]["relevance_stats"] = {
            "stats": {"field": "relevance_score"}
        }
        
        try:
            result = self.es.search(index=self.findings_index, body=body)
            
            aggregations = {}
            for key, value in result['aggregations'].items():
                if 'buckets' in value:
                    aggregations[key] = value['buckets']
                else:
                    aggregations[key] = value
            
            return aggregations
        except Exception as e:
            self.logger.error(f"Aggregation error: {e}")
            return {}
    
    def get_findings_timeline(self, job_id: str, interval: str = "1h") -> List[Dict]:
        """Get findings timeline histogram"""
        body = {
            "size": 0,
            "query": {"term": {"job_id": job_id}},
            "aggs": {
                "timeline": {
                    "date_histogram": {
                        "field": "created_at",
                        "calendar_interval": interval,
                        "min_doc_count": 0
                    }
                }
            }
        }
        
        try:
            result = self.es.search(index=self.findings_index, body=body)
            return result['aggregations']['timeline']['buckets']
        except Exception as e:
            self.logger.error(f"Timeline error: {e}")
            return []
    
    # ============================================================
    # MODULE RUNS OPERATIONS
    # ============================================================
    
    def index_module_run(self, module_run_id: str, run_data: Dict) -> bool:
        """Index module run execution data"""
        try:
            if 'started_at' in run_data and isinstance(run_data['started_at'], datetime):
                run_data['started_at'] = run_data['started_at'].isoformat()
            if 'finished_at' in run_data and isinstance(run_data['finished_at'], datetime):
                run_data['finished_at'] = run_data['finished_at'].isoformat()
            
            self.es.index(
                index=self.module_runs_index,
                id=module_run_id,
                document=run_data
            )
            return True
        except Exception as e:
            self.logger.error(f"Error indexing module run: {e}")
            return False
    
    def get_module_runs(self, job_id: str, size: int = 100) -> List[Dict]:
        """Get module runs for a job"""
        body = {
            "size": size,
            "query": {"term": {"job_id": job_id}},
            "sort": [{"created_at": {"order": "desc"}}]
        }
        
        try:
            result = self.es.search(index=self.module_runs_index, body=body)
            return [hit['_source'] for hit in result['hits']['hits']]
        except Exception as e:
            self.logger.error(f"Error getting module runs: {e}")
            return []
    
    # ============================================================
    # DELETION OPERATIONS
    # ============================================================
    
    def delete_findings_by_job(self, job_id: str) -> int:
        """Delete all findings for a job"""
        try:
            result = self.es.delete_by_query(
                index=self.findings_index,
                body={"query": {"term": {"job_id": job_id}}}
            )
            return result['deleted']
        except Exception as e:
            self.logger.error(f"Error deleting findings: {e}")
            return 0
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def refresh_index(self, index_name: Optional[str] = None):
        """Force refresh of index"""
        if index_name:
            self.es.indices.refresh(index=index_name)
        else:
            self.es.indices.refresh(index=self.findings_index)
            self.es.indices.refresh(index=self.module_runs_index)
    
    def health_check(self) -> bool:
        """Check Elasticsearch cluster health"""
        try:
            health = self.es.cluster.health()
            return health['status'] in ['green', 'yellow']
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    def get_index_stats(self, index_name: str) -> Dict:
        """Get index statistics"""
        try:
            stats = self.es.indices.stats(index=index_name)
            return stats['indices'][index_name]
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {}
