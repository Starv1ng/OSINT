# services/worker/tasks/modules/utils/input_analyzer.py

import re
from typing import Dict, List, Set, Tuple
from enum import Enum


class InputType(Enum):
    """Tipos de input detectados"""
    PERSON_NAME = "person_name"
    EMAIL = "email"
    PHONE = "phone"
    USERNAME = "username"
    DOMAIN = "domain"
    URL = "url"
    IP_ADDRESS = "ip_address"
    HASH = "hash"
    COMPANY = "company"
    UNKNOWN = "unknown"


class InputAnalyzer:
    """Analiza el input y determina qué módulos deben ejecutarse"""
    
    @staticmethod
    def analyze(query: str) -> Dict:
        """
        Analiza el input y retorna información útil para enrutar módulos
        
        Returns:
            {
                'input_type': InputType,
                'primary_modules': [lista de módulos principales],
                'secondary_modules': [lista de módulos secundarios],
                'extracted_indicators': {emails, usernames, domains, etc},
                'confidence': float 0.0-1.0
            }
        """
        query = query.strip()
        
        # Detectar tipo de input
        input_type = InputAnalyzer._detect_type(query)
        
        # Determinar módulos según tipo
        primary = InputAnalyzer._get_primary_modules(input_type)
        secondary = InputAnalyzer._get_secondary_modules(input_type)
        
        # Extraer indicadores secundarios
        indicators = InputAnalyzer._extract_indicators(query)
        
        # Confianza
        confidence = InputAnalyzer._get_confidence(input_type, query)
        
        return {
            'input_type': input_type.value,
            'primary_modules': primary,
            'secondary_modules': secondary,
            'extracted_indicators': indicators,
            'confidence': confidence,
            'query': query
        }
    
    @staticmethod
    def _detect_type(query: str) -> InputType:
        """Detecta el tipo de input"""
        query_lower = query.lower().strip()
        
        # EMAIL
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', query_lower):
            return InputType.EMAIL
        
        # PHONE (patrones comunes)
        if re.match(r'^(\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?[2-9]\d{2}[-.\s]?\d{4}$', query):
            return InputType.PHONE
        
        # IP ADDRESS
        if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', query):
            parts = query.split('.')
            if all(0 <= int(p) <= 255 for p in parts):
                return InputType.IP_ADDRESS
        
        # URL
        if query.startswith(('http://', 'https://', 'www.')):
            return InputType.URL
        
        # DOMAIN
        if re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$', query_lower):
            if '.' in query and '@' not in query and '/' not in query:
                return InputType.DOMAIN
        
        # USERNAME (sin espacios, contiene @, _, o -)
        if len(query) < 30 and not ' ' in query and re.match(r'^[a-zA-Z0-9_.-]{3,}$', query):
            # Podría ser username si no tiene puntos consecutivos
            if '..' not in query and '--' not in query:
                return InputType.USERNAME
        
        # HASH (32, 40, 64, 128 caracteres hex)
        if re.match(r'^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{40}$|^[a-fA-F0-9]{64}$|^[a-fA-F0-9]{128}$', query):
            return InputType.HASH
        
        # PERSON NAME (tiene espacios y letras)
        if ' ' in query and len(query) > 2 and re.match(r'^[a-zA-Z\s\'-]+$', query):
            # Validar que no sea solo una palabra muy larga
            words = query.split()
            if len(words) >= 2 and all(len(w) >= 2 for w in words):
                return InputType.PERSON_NAME
        
        # COMPANY (palabra única larga, o frase con palabras claves)
        if any(keyword in query_lower for keyword in ['inc', 'ltd', 'corp', 'company', 'group', 'systems']):
            return InputType.COMPANY
        
        return InputType.UNKNOWN
    
    @staticmethod
    def _get_primary_modules(input_type: InputType) -> List[str]:
        """Retorna los módulos principales según el tipo de input"""
        
        modules_by_type = {
            InputType.PERSON_NAME: [
                'TwitterSearcher',
                'LinkedInSearcher',
                'GitHubSearcher',
                'SearchEngineSearcher',
                'WebSpider',
                'SelectiveCrawler',
            ],
            InputType.EMAIL: [
                'EmailVerifier',
                'BreachSearcher',
                'SearchEngineSearcher',
                'LinkedInSearcher',
                'TwitterSearcher',
            ],
            InputType.PHONE: [
                'PhoneVerifier',
                'SearchEngineSearcher',
                'BreachSearcher',
            ],
            InputType.USERNAME: [
                'TwitterSearcher',
                'GitHubSearcher',
                'LinkedInSearcher',
                'SearchEngineSearcher',
                'InstagramSearcher',
            ],
            InputType.DOMAIN: [
                'DomainIntelligenceSearcher',
                'DNSWhoisSearcher',
                'WebSpider',
                'SelectiveCrawler',
                'SearchEngineSearcher',
            ],
            InputType.URL: [
                'WebSpider',
                'SelectiveCrawler',
                'SearchEngineSearcher',
            ],
            InputType.IP_ADDRESS: [
                'DNSWhoisSearcher',
                'SearchEngineSearcher',
            ],
            InputType.HASH: [
                'SearchEngineSearcher',
                'BreachSearcher',
            ],
            InputType.COMPANY: [
                'SearchEngineSearcher',
                'LinkedInSearcher',
                'WebSpider',
                'SelectiveCrawler',
            ],
            InputType.UNKNOWN: [
                'SearchEngineSearcher',
                'WebSpider',
            ],
        }
        
        return modules_by_type.get(input_type, ['SearchEngineSearcher'])
    
    @staticmethod
    def _get_secondary_modules(input_type: InputType) -> List[str]:
        """Retorna módulos secundarios útiles como fallback"""
        
        # Módulos que siempre son útiles de ejecutar
        return [
            'SearchEngineSearcher',
            'WebSpider',
        ]
    
    @staticmethod
    def _extract_indicators(query: str) -> Dict[str, Set[str]]:
        """Extrae indicadores secundarios del query"""
        indicators = {
            'emails': set(),
            'usernames': set(),
            'domains': set(),
            'urls': set(),
        }
        
        # Buscar emails en el query
        emails = re.findall(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', query)
        indicators['emails'].update(emails)
        
        # Buscar URLs
        urls = re.findall(r'https?://[^\s]+|www\.[^\s]+', query)
        indicators['urls'].update(urls)
        
        # Buscar menciones de Twitter/redes sociales
        usernames = re.findall(r'@([a-zA-Z0-9_]+)', query)
        indicators['usernames'].update(usernames)
        
        # Buscar dominios
        domains = re.findall(r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}', query)
        indicators['domains'].update(domains)
        
        # Convertir sets a sorted lists
        return {
            'emails': sorted(list(indicators['emails'])),
            'usernames': sorted(list(indicators['usernames'])),
            'domains': sorted(list(indicators['domains'])),
            'urls': sorted(list(indicators['urls'])),
        }
    
    @staticmethod
    def _get_confidence(input_type: InputType, query: str) -> float:
        """Calcula confianza en la detección"""
        
        confidence_map = {
            InputType.EMAIL: 0.99,
            InputType.IP_ADDRESS: 0.98,
            InputType.HASH: 0.97,
            InputType.PHONE: 0.85,
            InputType.DOMAIN: 0.90,
            InputType.URL: 0.95,
            InputType.PERSON_NAME: 0.80,
            InputType.USERNAME: 0.75,
            InputType.COMPANY: 0.70,
            InputType.UNKNOWN: 0.30,
        }
        
        base_confidence = confidence_map.get(input_type, 0.5)
        
        # Ajustar confianza según longitud
        if input_type == InputType.PERSON_NAME:
            words = query.split()
            if len(words) >= 2:
                base_confidence += 0.05
        
        return min(base_confidence, 1.0)
    
    @staticmethod
    def get_module_names() -> List[str]:
        """Retorna lista de todos los módulos disponibles"""
        return [
            'TwitterSearcher',
            'LinkedInSearcher',
            'GitHubSearcher',
            'SearchEngineSearcher',
            'EmailVerifier',
            'PhoneVerifier',
            'BreachSearcher',
            'DomainIntelligenceSearcher',
            'DNSWhoisSearcher',
            'WebSpider',
            'SelectiveCrawler',
            'InstagramSearcher',
        ]
    
    @staticmethod
    def map_module_to_class(module_name: str) -> str:
        """Mapea nombre de módulo a clase Python"""
        module_map = {
            'TwitterSearcher': 'modules.social_media.twitter_searcher.TwitterSearcher',
            'LinkedInSearcher': 'modules.social_media.linkedin_searcher.LinkedInSearcher',
            'GitHubSearcher': 'modules.development.github_searcher.GitHubSearcher',
            'SearchEngineSearcher': 'modules.search_engine.search_engine_searcher.SearchEngineSearcher',
            'EmailVerifier': 'modules.verification.email_verifier.EmailVerifier',
            'BreachSearcher': 'modules.security.breach_searcher.BreachSearcher',
            'DomainIntelligenceSearcher': 'modules.infrastructure.domain_intelligence_searcher.DomainIntelligenceSearcher',
            'DNSWhoisSearcher': 'modules.infrastructure.dns_whois_searcher.DNSWhoisSearcher',
            'WebSpider': 'modules.web.web_spider.WebSpider',
            'SelectiveCrawler': 'modules.web.selective_crawler.SelectiveCrawler',
        }
        return module_map.get(module_name, '')
