"""
PostgreSQL Client for OSINT v2.0
Handles all database operations for findings, indicators, deduplication, and audit
"""

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor, execute_values
from typing import List, Dict, Optional, Any, Tuple
import json
from datetime import datetime
import logging
import hashlib
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PostgreSQLClient:
    """PostgreSQL client with connection pooling and transaction support"""
    
    def __init__(self, database_url: str, pool_size: int = 20):
        """
        Initialize PostgreSQL client with connection pool
        
        Args:
            database_url: PostgreSQL connection string
            pool_size: Maximum number of connections in pool
        """
        self.pool = SimpleConnectionPool(1, pool_size, database_url)
        self.logger = logging.getLogger(__name__)
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Database error: {e}")
            raise
        finally:
            self.pool.putconn(conn)
    
    # ============================================================
    # FINDINGS OPERATIONS
    # ============================================================
    
    def create_finding(self, finding_data: Dict) -> str:
        """
        Create a new finding
        
        Args:
            finding_data: Dictionary with finding information
                Required: job_id, module_name, type, value, normalized_value
                Optional: confidence, relevance_score, metadata, etc.
        
        Returns:
            finding_id (UUID as string)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO findings (
                    job_id, module_run_id, module_name, type, value, 
                    normalized_value, confidence, relevance_score, 
                    iteration, source_url, raw_text, metadata, tags, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING finding_id
            """, (
                finding_data['job_id'],
                finding_data.get('module_run_id'),
                finding_data['module_name'],
                finding_data['type'],
                finding_data['value'],
                finding_data['normalized_value'],
                finding_data.get('confidence', 0.5),
                finding_data.get('relevance_score', 0.5),
                finding_data.get('iteration', 1),
                finding_data.get('source_url'),
                finding_data.get('raw_text'),
                json.dumps(finding_data.get('metadata', {})),
                finding_data.get('tags', []),
                finding_data.get('created_by', 'system')
            ))
            finding_id = cursor.fetchone()[0]
            return str(finding_id)
    
    def bulk_create_findings(self, findings: List[Dict]) -> List[str]:
        """Bulk insert findings for better performance"""
        if not findings:
            return []
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            values = [
                (
                    f['job_id'], f.get('module_run_id'), f['module_name'],
                    f['type'], f['value'], f['normalized_value'],
                    f.get('confidence', 0.5), f.get('relevance_score', 0.5),
                    f.get('iteration', 1), f.get('source_url'), f.get('raw_text'),
                    json.dumps(f.get('metadata', {})), f.get('tags', []),
                    f.get('created_by', 'system')
                )
                for f in findings
            ]
            
            result = execute_values(
                cursor,
                """
                INSERT INTO findings (
                    job_id, module_run_id, module_name, type, value, 
                    normalized_value, confidence, relevance_score, 
                    iteration, source_url, raw_text, metadata, tags, created_by
                ) VALUES %s
                RETURNING finding_id
                """,
                values,
                fetch=True
            )
            return [str(row[0]) for row in result]
    
    def get_findings(
        self, 
        job_id: str, 
        filters: Optional[Dict] = None,
        limit: int = 100, 
        offset: int = 0
    ) -> List[Dict]:
        """
        Get findings for a job with optional filters
        
        Args:
            job_id: Job identifier
            filters: Optional filters (module_name, type, min_confidence, etc.)
            limit: Maximum results
            offset: Results offset for pagination
        
        Returns:
            List of finding dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT 
                    finding_id, job_id, module_run_id, module_name, type, 
                    value, normalized_value, confidence, relevance_score,
                    verified, iteration, source_url, metadata, tags,
                    created_at, updated_at
                FROM findings
                WHERE job_id = %s AND soft_deleted = false
            """
            params = [job_id]
            
            if filters:
                if 'module_name' in filters:
                    query += " AND module_name = %s"
                    params.append(filters['module_name'])
                if 'type' in filters:
                    query += " AND type = %s"
                    params.append(filters['type'])
                if 'min_confidence' in filters:
                    query += " AND confidence >= %s"
                    params.append(filters['min_confidence'])
            
            query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_finding_by_id(self, finding_id: str) -> Optional[Dict]:
        """Get single finding by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM findings WHERE finding_id = %s
            """, (finding_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_finding(self, finding_id: str, updates: Dict) -> bool:
        """Update finding fields"""
        if not updates:
            return False
        
        allowed_fields = [
            'confidence', 'relevance_score', 'verified', 'verified_by',
            'verified_at', 'tags', 'metadata', 'soft_deleted'
        ]
        
        set_clauses = []
        params = []
        for field, value in updates.items():
            if field in allowed_fields:
                if field == 'metadata':
                    set_clauses.append(f"{field} = %s")
                    params.append(json.dumps(value))
                else:
                    set_clauses.append(f"{field} = %s")
                    params.append(value)
        
        if not set_clauses:
            return False
        
        params.append(finding_id)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = f"UPDATE findings SET {', '.join(set_clauses)} WHERE finding_id = %s"
            cursor.execute(query, params)
            return cursor.rowcount > 0
    
    # ============================================================
    # INDICATORS OPERATIONS
    # ============================================================
    
    def create_indicator(self, indicator_data: Dict) -> str:
        """Create indicator from finding"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO indicators (
                    type, value, normalized_value, data_type,
                    source_finding_id, confidence, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (normalized_value, type) DO UPDATE SET
                    last_seen = CURRENT_TIMESTAMP,
                    occurrence_count = indicators.occurrence_count + 1
                RETURNING indicator_id
            """, (
                indicator_data['type'],
                indicator_data['value'],
                indicator_data['normalized_value'],
                indicator_data.get('data_type'),
                indicator_data.get('source_finding_id'),
                indicator_data.get('confidence', 0.5),
                indicator_data.get('created_by', 'system')
            ))
            result = cursor.fetchone()
            return str(result[0]) if result else None
    
    def get_indicators_by_finding(self, finding_id: str) -> List[Dict]:
        """Get all indicators extracted from a finding"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM indicators
                WHERE source_finding_id = %s
                ORDER BY created_at DESC
            """, (finding_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_indicators_by_job(self, job_id: str) -> List[Dict]:
        """Get all indicators for a job"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT DISTINCT i.*
                FROM indicators i
                JOIN findings f ON f.finding_id = i.source_finding_id
                WHERE f.job_id = %s
                ORDER BY i.first_seen DESC
            """, (job_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ============================================================
    # DEDUPLICATION OPERATIONS
    # ============================================================
    
    def check_dedup_exists(self, job_id: str, indicator_hash: str) -> bool:
        """Check if indicator already exists for this job"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM job_deduplication
                    WHERE job_id = %s AND indicator_hash = %s
                )
            """, (job_id, indicator_hash))
            return cursor.fetchone()[0]
    
    def record_dedup(self, job_id: str, indicator_hash: str, finding_id: str) -> bool:
        """Record deduplication entry"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO job_deduplication (job_id, indicator_hash, finding_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (job_id, indicator_hash) DO NOTHING
                """, (job_id, indicator_hash, finding_id))
                return True
        except Exception as e:
            self.logger.error(f"Dedup record error: {e}")
            return False
    
    def compute_finding_hash(self, finding_data: Dict) -> str:
        """Compute hash for finding deduplication"""
        key_fields = [
            finding_data.get('normalized_value', ''),
            finding_data.get('type', ''),
            finding_data.get('module_name', '')
        ]
        hash_input = '|'.join(str(f) for f in key_fields)
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    # ============================================================
    # MODULE RUNS OPERATIONS
    # ============================================================
    
    def create_module_run(self, run_data: Dict) -> str:
        """Create module run record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO module_runs (
                    job_id, module_name, module_version, status, started_at
                ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                RETURNING module_run_id
            """, (
                run_data['job_id'],
                run_data['module_name'],
                run_data.get('module_version', '1.0'),
                'started'
            ))
            return str(cursor.fetchone()[0])
    
    def update_module_run(self, module_run_id: str, updates: Dict) -> bool:
        """Update module run with results"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE module_runs
                SET status = %s,
                    finished_at = CURRENT_TIMESTAMP,
                    duration_ms = %s,
                    findings_count = %s,
                    items_processed = %s,
                    errors = %s,
                    raw_result = %s
                WHERE module_run_id = %s
            """, (
                updates.get('status', 'completed'),
                updates.get('duration_ms'),
                updates.get('findings_count', 0),
                updates.get('items_processed', 0),
                updates.get('errors'),
                json.dumps(updates.get('raw_result', {})),
                module_run_id
            ))
            return cursor.rowcount > 0
    
    def get_module_runs(self, job_id: str) -> List[Dict]:
        """Get all module runs for a job"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM module_runs
                WHERE job_id = %s
                ORDER BY created_at DESC
            """, (job_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ============================================================
    # AUDIT LOG OPERATIONS
    # ============================================================
    
    def create_audit_log(self, log_data: Dict) -> str:
        """Create audit log entry"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_log (
                    user_id, action, resource_type, resource_id,
                    old_values, new_values, ip_address, user_agent
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING log_id
            """, (
                log_data.get('user_id'),
                log_data['action'],
                log_data['resource_type'],
                log_data['resource_id'],
                json.dumps(log_data.get('old_values', {})),
                json.dumps(log_data.get('new_values', {})),
                log_data.get('ip_address'),
                log_data.get('user_agent')
            ))
            return str(cursor.fetchone()[0])
    
    # ============================================================
    # STATISTICS & ANALYTICS
    # ============================================================
    
    def get_job_statistics(self, job_id: str) -> Dict:
        """Get comprehensive job statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM v_job_statistics WHERE job_id = %s
            """, (job_id,))
            row = cursor.fetchone()
            return dict(row) if row else {}
    
    def get_findings_count(self, job_id: str, filters: Optional[Dict] = None) -> int:
        """Get total findings count with optional filters"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT COUNT(*) FROM findings WHERE job_id = %s AND soft_deleted = false"
            params = [job_id]
            
            if filters:
                if 'type' in filters:
                    query += " AND type = %s"
                    params.append(filters['type'])
                if 'min_confidence' in filters:
                    query += " AND confidence >= %s"
                    params.append(filters['min_confidence'])
            
            cursor.execute(query, params)
            return cursor.fetchone()[0]
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def health_check(self) -> bool:
        """Check database connection health"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return cursor.fetchone()[0] == 1
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    def close(self):
        """Close all connections in pool"""
        self.pool.closeall()
