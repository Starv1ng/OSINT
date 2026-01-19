# services/worker/config/dynamic_search_config.py

"""
Configuración para búsquedas dinámicas iterativas
"""

# Número máximo de iteraciones
MAX_ITERATIONS = 5

# Umbral de relevancia (0-1) para nuevos indicadores
RELEVANCE_THRESHOLD = 0.5

# Máximo de workers paralelos
MAX_WORKERS = 3

# Mapeo de tipos de indicadores a módulos que los procesan
INDICATOR_MODULE_MAPPING = {
    'email': ['email_verifier', 'breach', 'dns_whois', 'linkedin', 'github'],
    'username': ['twitter', 'linkedin', 'github', 'breach'],
    'phone': ['dns_whois', 'search'],
    'domain': ['dns_whois', 'domain_intelligence'],
    'url': ['selective_crawler', 'webspider'],
    'ip': ['dns_whois'],
    'social_profile': ['twitter', 'linkedin', 'github'],
    'company': ['linkedin', 'github', 'search'],
    'name': ['twitter', 'linkedin', 'github'],
}

# Módulos iniciales por tipo de búsqueda
INITIAL_MODULES_BY_TYPE = {
    "person": ["search", "webspider"],
    "email": ["search", "email_verifier"],
    "phone": ["search", "dns_whois"],
    "username": ["search", "twitter"],
    "company": ["search", "linkedin"],
    "domain": ["dns_whois", "domain_intelligence"],
    "general": ["search", "webspider"]
}

# Límites de ejecución
MAX_URLS_PER_ITERATION = 10
MAX_INDICATORS_PER_TYPE = 50
MAX_FINDINGS_PER_ITERATION = 1000

# Timeouts
MODULE_TIMEOUT_SECONDS = 30
TOTAL_SEARCH_TIMEOUT_SECONDS = 300

# Deduplicación
DUPLICATE_CHECK_WINDOW = 1000  # Últimos N hallazgos a verificar

# Logging
LOG_ITERATION_DETAILS = True
LOG_INDICATOR_EXTRACTION = True
LOG_MODULE_SELECTION = True

# Modos de ejecución
EXECUTION_MODES = {
    'aggressive': {
        'max_iterations': 7,
        'relevance_threshold': 0.3,
        'max_workers': 5,
    },
    'normal': {
        'max_iterations': 5,
        'relevance_threshold': 0.5,
        'max_workers': 3,
    },
    'conservative': {
        'max_iterations': 3,
        'relevance_threshold': 0.7,
        'max_workers': 2,
    }
}
