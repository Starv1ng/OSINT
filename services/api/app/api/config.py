import os

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://dev:devpass@postgres:5432/osint")
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

settings = Settings()

