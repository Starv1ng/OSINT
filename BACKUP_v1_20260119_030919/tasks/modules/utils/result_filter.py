# services/worker/tasks/modules/utils/result_filter.py

import re
from typing import List, Dict, Any, Set, Optional
from urllib.parse import urlparse, parse_qs


class ResultFilter:
    """Filtro inteligente para eliminar resultados irrelevantes y ruido de datos OSINT"""
    
    # Patrones a ignorar
    SPAM_PATTERNS = [
        r'[&\?][a-z0-9]{10,}=[a-f0-9]{32,}',  # Parámetros hash largos (rut=...)
        r'/\?q=',  # URLs de búsqueda con query params
        r'&norw=',  # Parámetros de búsqueda
        r'&rut=',  # Token de tracking
        r'__',  # Parámetros internos
        r'/html/\?',  # URLs de resultado HTML
    ]
    
    # Dominios de búsqueda (no son resultados reales)
    SEARCH_ENGINE_DOMAINS = {
        'google.com', 'bing.com', 'duckduckgo.com', 'baidu.com',
        'yandex.com', 'yahoo.com', 'ask.com', 'aol.com'
    }
    
    # Dominios técnicos que no aportan info de persona
    TECHNICAL_DOMAINS = {
        'w3.org', 'mozilla.org', 'w3schools.com', 'stackoverflow.com',
        'github.com/search', 'npmjs.com', 'pypi.org', 'crates.io'
    }
    
    # Atributos HTML que no son resultados
    NOISE_KEYWORDS = {
        'twitter.com/intent',  # Tweet intents, not actual profiles
        'twitter.com/share',   # Share buttons
        'twitter.com/search',  # Search results, not profiles
        '/html/',              # Generic HTML paths
        'type=', 'id=', 'nr=', 'wrapped=', 'context=',  # HTML attributes
        'seenerror', 'original',  # Internal HTML fields
    }
    
    @staticmethod
    def clean_findings(findings: List[Dict[str, Any]], query: str = '') -> List[Dict[str, Any]]:
        """Limpia y filtra hallazgos irrelevantes"""
        if not findings:
            return []
        
        cleaned = []
        seen_values = set()
        
        for finding in findings:
            # Skip if already seen (deduplication)
            value = str(finding.get('value', '')).lower()
            if value in seen_values:
                continue
            
            # Skip if fails validation
            if not ResultFilter.is_valid_finding(finding, query):
                continue
            
            seen_values.add(value)
            cleaned.append(finding)
        
        return cleaned
    
    @staticmethod
    def is_valid_finding(finding: Dict[str, Any], query: str = '') -> bool:
        """Determina si un hallazgo es válido y relevante"""
        value = str(finding.get('value', '')).strip()
        finding_type = finding.get('type', '').lower()
        
        if not value:
            return False
        
        # Filtros por tipo
        if finding_type == 'link' or finding_type == 'url':
            return ResultFilter._is_valid_url(value, query)
        elif finding_type == 'email':
            return ResultFilter._is_valid_email(value)
        elif finding_type == 'username':
            return ResultFilter._is_valid_username(value)
        elif finding_type == 'social_profile':
            return ResultFilter._is_valid_social_profile(value)
        elif finding_type == 'raw_page':
            return ResultFilter._is_valid_url(value, query)
        elif finding_type == 'phone':
            return ResultFilter._is_valid_phone(value)
        
        # Por defecto, aceptar si no es vacío
        return len(value) > 2
    
    @staticmethod
    def _is_valid_url(url: str, query: str = '') -> bool:
        """Valida URLs filtrando spam y parámetros inútiles"""
        url_lower = url.lower()
        
        # Rechazar URLs con patrones de spam
        for pattern in ResultFilter.SPAM_PATTERNS:
            if re.search(pattern, url_lower):
                return False
        
        # Rechazar URLs con ruido keyword
        for keyword in ResultFilter.NOISE_KEYWORDS:
            if keyword in url_lower:
                return False
        
        # Rechazar URLs de search engines (no son resultados reales)
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Limpieza de www
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Rechazar dominios de búsqueda
            for search_domain in ResultFilter.SEARCH_ENGINE_DOMAINS:
                if domain.endswith(search_domain):
                    return False
            
            # Rechazar dominios técnicos
            for tech_domain in ResultFilter.TECHNICAL_DOMAINS:
                if tech_domain in domain:
                    return False
        except:
            return False
        
        # Validar que tenga estructura mínima
        if not url.startswith(('http://', 'https://', 'www.')):
            return False
        
        # Rechazar URLs demasiado cortas o largas
        if len(url) < 15 or len(url) > 500:
            return False
        
        # Rechazar URLs con demasiados parámetros
        if url.count('&') > 5 or url.count('?') > 3:
            return False
        
        return True
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Valida direcciones de email"""
        # Patrón simple pero efectivo
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False
        
        # Rechazar emails de prueba o genéricos (solo dominios específicos)
        bad_domains = ['@test.', '@localhost.', '@temp.', 'noreply@']
        for bad in bad_domains:
            if bad in email.lower():
                return False
        
        return True
    
    @staticmethod
    def _is_valid_username(username: str) -> bool:
        """Valida nombres de usuario"""
        # Longitud válida
        if len(username) < 3 or len(username) > 30:
            return False
        
        # Debe contener caracteres alfanuméricos
        if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
            return False
        
        # No puede ser genérico
        generic = ['admin', 'user', 'test', 'root', 'guest']
        if username.lower() in generic:
            return False
        
        return True
    
    @staticmethod
    def _is_valid_social_profile(url: str) -> bool:
        """Valida perfiles de redes sociales"""
        url_lower = url.lower()
        
        # Rechazar patrones de ruido específicos
        bad_patterns = [
            r'twitter\.com/[0-9]+(?:/|$)',      # twitter.com/31, /45, etc
            r'twitter\.com/(intent|share|search)',
            r'twitter\.com/(id|type|nr|context|wrapped|original|seenerror)',  # HTML attributes
            r'type=', r'id=', r'nr=', r'wrapped=', r'context=', r'seenerror',  # HTML params
        ]
        
        for pattern in bad_patterns:
            if re.search(pattern, url_lower):
                return False
        
        # Username debe ser alfanumérico o guiones (no solo números o palabras clave HTML)
        m = re.search(r'twitter\.com/([a-z0-9_]+)', url_lower)
        if m:
            username = m.group(1)
            # Rechazar si es solo números o palabras reservadas
            if username.isdigit() or username in ['intent', 'share', 'search', 'home', 'explore', 'messages', 'notifications', 'abc']:
                return False
            # Rechazar si es demasiado corto o solo mayúsculas (típicamente ruido)
            if len(username) < 3:
                return False
            # Si es mayúsculas puro, probablemente sea un atributo HTML
            if username.isupper() and len(username) <= 3:
                return False
            return True
        
        # Validar estructura de otros perfiles
        social_patterns = [
            r'instagram\.com/(?!explore|accounts)[a-z0-9_.-]+/?$',
            r'github\.com/[a-z0-9-]+/?$',
            r'linkedin\.com/in/[a-z0-9-]+/?$',
            r'facebook\.com/[a-z0-9.]+/?$',
        ]
        
        for pattern in social_patterns:
            if re.search(pattern, url_lower):
                return True
        
        return False
    
    @staticmethod
    def _is_valid_phone(phone: str) -> bool:
        """Valida números de teléfono"""
        # Eliminar espacios, guiones, paréntesis
        clean = re.sub(r'[\s\-()]+', '', phone)
        
        # Debe tener 7-15 dígitos
        if not re.match(r'^\+?[0-9]{7,15}$', clean):
            return False
        
        return True
    
    @staticmethod
    def extract_emails(text: str) -> Set[str]:
        """Extrae emails válidos de texto"""
        pattern = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
        matches = re.findall(pattern, text)
        
        # Filtrar emails inválidos
        valid = set()
        for email in matches:
            if ResultFilter._is_valid_email(email):
                valid.add(email)
        
        return valid
    
    @staticmethod
    def extract_usernames(text: str, context: str = '') -> Set[str]:
        """Extrae nombres de usuario probables de texto"""
        # Patrones para nombres de usuario
        patterns = [
            r'(?:@|handle:|username:)\s*([a-zA-Z0-9_]+)',  # @mention o explicit
            r'/(?:users?|profiles?|author|u)/([a-zA-Z0-9_-]+)',  # Path-based
            r'(?:github|twitter|instagram|linkedin)\.com/([a-zA-Z0-9_-]+)',  # Social profiles
        ]
        
        usernames = set()
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if ResultFilter._is_valid_username(match):
                    usernames.add(match)
        
        return usernames
    
    @staticmethod
    def extract_urls(text: str, filter_spam: bool = True) -> Set[str]:
        """Extrae URLs de texto"""
        pattern = r'https?://[^\s<>"\)}\]]+|www\.[^\s<>"\)}\]]+\.[a-z]{2,}'
        urls = set(re.findall(pattern, text))
        
        if filter_spam:
            urls = {u for u in urls if ResultFilter._is_valid_url(u)}
        
        return urls
    
    @staticmethod
    def group_findings_by_type(findings: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Agrupa hallazgos por tipo"""
        grouped = {}
        for finding in findings:
            ftype = finding.get('type', 'unknown')
            if ftype not in grouped:
                grouped[ftype] = []
            grouped[ftype].append(finding)
        
        return grouped
    
    @staticmethod
    def deduplicate_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplica hallazgos manteniendo el primer encuentro de cada valor"""
        seen = set()
        unique = []
        
        for finding in findings:
            value = str(finding.get('value', '')).lower().strip()
            if value not in seen:
                seen.add(value)
                unique.append(finding)
        
        return unique
