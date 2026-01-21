"""
Centralized configuration management for OSINT Worker
"""
import os
from dataclasses import dataclass
from typing import Tuple


@dataclass
class DatabaseConfig:
    """PostgreSQL database configuration"""
    url: str = os.environ.get(
        "DATABASE_URL",
        "postgresql://dev:devpass@postgres:5432/osint"
    )
    pool_size: int = int(os.environ.get("DB_POOL_SIZE", "20"))


@dataclass
class ElasticsearchConfig:
    """Elasticsearch configuration"""
    host: str = os.environ.get(
        "ELASTICSEARCH_HOST",
        "http://elasticsearch:9200"
    )
    timeout: int = int(os.environ.get("ES_TIMEOUT", "30"))
    findings_index: str = os.environ.get("ES_FINDINGS_INDEX", "findings-v2")
    module_runs_index: str = os.environ.get("ES_MODULE_RUNS_INDEX", "module-runs-v2")


@dataclass
class Neo4jConfig:
    """Neo4j graph database configuration"""
    uri: str = os.environ.get(
        "NEO4J_URI",
        "bolt://neo4j:7687"
    )
    user: str = os.environ.get("NEO4J_USER", "neo4j")
    password: str = os.environ.get("NEO4J_PASSWORD", "password123")
    
    @property
    def auth(self) -> Tuple[str, str]:
        """Return authentication tuple"""
        return (self.user, self.password)


@dataclass
class OrchestratorConfig:
    """Dynamic orchestrator configuration"""
    max_iterations: int = int(os.environ.get("MAX_ITERATIONS", "5"))
    relevance_threshold: float = float(os.environ.get("RELEVANCE_THRESHOLD", "0.5"))
    execution_mode: str = os.environ.get("EXECUTION_MODE", "normal")
    max_workers: int = int(os.environ.get("ORCHESTRATOR_MAX_WORKERS", "3"))


@dataclass
class CeleryConfig:
    """Celery task broker configuration"""
    broker_url: str = os.environ.get(
        "CELERY_BROKER_URL",
        "redis://redis:6379/0"
    )
    result_backend: str = os.environ.get(
        "CELERY_RESULT_BACKEND",
        "redis://redis:6379/1"
    )
    task_timeout: int = int(os.environ.get("CELERY_TASK_TIMEOUT", "3600"))
    task_max_retries: int = int(os.environ.get("CELERY_MAX_RETRIES", "3"))


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = os.environ.get("LOG_LEVEL", "INFO")
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class AppConfig:
    """Main application configuration (singleton)"""
    database: DatabaseConfig = None
    elasticsearch: ElasticsearchConfig = None
    neo4j: Neo4jConfig = None
    orchestrator: OrchestratorConfig = None
    celery: CeleryConfig = None
    logging: LoggingConfig = None
    
    def __post_init__(self):
        """Initialize all sub-configs with defaults if not provided"""
        if self.database is None:
            self.database = DatabaseConfig()
        if self.elasticsearch is None:
            self.elasticsearch = ElasticsearchConfig()
        if self.neo4j is None:
            self.neo4j = Neo4jConfig()
        if self.orchestrator is None:
            self.orchestrator = OrchestratorConfig()
        if self.celery is None:
            self.celery = CeleryConfig()
        if self.logging is None:
            self.logging = LoggingConfig()


# Global singleton instance
config = AppConfig()
