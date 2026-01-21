"""
Centralized configuration for OSINT API Gateway
"""
import os
from dataclasses import dataclass
from typing import Tuple


@dataclass
class DatabaseConfig:
    """PostgreSQL database configuration"""
    url: str = os.getenv("DATABASE_URL", "postgresql://dev:devpass@postgres:5432/osint")
    pool_size: int = int(os.getenv("DB_POOL_SIZE", "20"))


@dataclass
class ElasticsearchConfig:
    """Elasticsearch configuration"""
    host: str = os.getenv("ELASTICSEARCH_HOST", "http://elasticsearch:9200")
    timeout: int = int(os.getenv("ES_TIMEOUT", "30"))
    findings_index: str = os.getenv("ES_FINDINGS_INDEX", "findings-v2")
    module_runs_index: str = os.getenv("ES_MODULE_RUNS_INDEX", "module-runs-v2")


@dataclass
class Neo4jConfig:
    """Neo4j graph database configuration"""
    uri: str = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    user: str = os.getenv("NEO4J_USER", "neo4j")
    password: str = os.getenv("NEO4J_PASSWORD", "password123")
    
    @property
    def auth(self) -> Tuple[str, str]:
        """Return authentication tuple"""
        return (self.user, self.password)


@dataclass
class RedisConfig:
    """Redis cache and broker configuration"""
    url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    celery_broker: str = os.getenv("CELERY_BROKER", "redis://redis:6379/0")


@dataclass
class OrchestratorConfig:
    """Dynamic orchestrator configuration"""
    max_iterations: int = int(os.getenv("MAX_ITERATIONS", "5"))
    relevance_threshold: float = float(os.getenv("RELEVANCE_THRESHOLD", "0.5"))
    execution_mode: str = os.getenv("EXECUTION_MODE", "normal")
    default_confidence_threshold: float = float(os.getenv("DEFAULT_CONFIDENCE_THRESHOLD", "0.5"))


@dataclass
class APIConfig:
    """API endpoint configuration"""
    pagination_limit: int = int(os.getenv("API_PAGINATION_LIMIT", "100"))
    max_limit: int = int(os.getenv("API_MAX_LIMIT", "1000"))
    request_timeout: int = int(os.getenv("API_REQUEST_TIMEOUT", "30"))


@dataclass
class Settings:
    """Main application settings (singleton)"""
    # Database configs
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://dev:devpass@postgres:5432/osint")
    
    # Service configs
    database: DatabaseConfig = None
    elasticsearch: ElasticsearchConfig = None
    neo4j: Neo4jConfig = None
    redis: RedisConfig = None
    orchestrator: OrchestratorConfig = None
    api: APIConfig = None
    
    # Legacy attributes for backwards compatibility
    ELASTICSEARCH_HOST: str = os.getenv("ELASTICSEARCH_HOST", "http://elasticsearch:9200")
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password123")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    CELERY_BROKER: str = os.getenv("CELERY_BROKER", "redis://redis:6379/0")
    
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "5"))
    RELEVANCE_THRESHOLD: float = float(os.getenv("RELEVANCE_THRESHOLD", "0.5"))
    EXECUTION_MODE: str = os.getenv("EXECUTION_MODE", "normal")
    DEFAULT_CONFIDENCE_THRESHOLD: float = float(os.getenv("DEFAULT_CONFIDENCE_THRESHOLD", "0.5"))
    
    API_PAGINATION_LIMIT: int = int(os.getenv("API_PAGINATION_LIMIT", "100"))
    API_MAX_LIMIT: int = int(os.getenv("API_MAX_LIMIT", "1000"))
    
    def __post_init__(self):
        """Initialize all sub-configs with defaults if not provided"""
        if self.database is None:
            self.database = DatabaseConfig()
        if self.elasticsearch is None:
            self.elasticsearch = ElasticsearchConfig()
        if self.neo4j is None:
            self.neo4j = Neo4jConfig()
        if self.redis is None:
            self.redis = RedisConfig()
        if self.orchestrator is None:
            self.orchestrator = OrchestratorConfig()
        if self.api is None:
            self.api = APIConfig()


# Global singleton instance
settings = Settings()
