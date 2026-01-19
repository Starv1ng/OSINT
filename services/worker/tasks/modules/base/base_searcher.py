# services/worker/tasks/modules/base/base_searcher.py

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import logging
import requests
from datetime import datetime
import re

class BaseSearcher(ABC):
    """Clase base para todos los módulos de búsqueda real"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    @abstractmethod
    def search(self, query: str, search_type: str, options: Dict = None) -> Dict[str, Any]:
        """Método principal de búsqueda - DEBE ser implementado"""
        pass
    
    @abstractmethod
    def get_supported_types(self) -> List[str]:
        """Tipos de búsqueda que soporta este módulo"""
        pass
    
    def get_priority(self) -> int:
        """Prioridad de ejecución"""
        return 10
    
    def is_enabled(self) -> bool:
        """Si el módulo está habilitado"""
        return True
    
    def _make_request(self, url: str, method: str = "GET", **kwargs) -> requests.Response:
        """Realizar petición HTTP con manejo de errores"""
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error en petición a {url}: {e}")
            raise
    
    def _extract_emails(self, text: str) -> List[str]:
        """Extraer emails de texto"""
        if not text:
            return []
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.findall(pattern, text)
    
    def _extract_phones(self, text: str) -> List[str]:
        """Extraer números de teléfono"""
        if not text:
            return []
        pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
        return re.findall(pattern, text)
    
    def _detect_social_platforms(self, url: str, text: str) -> List[tuple]:
        """Detectar plataformas de redes sociales"""
        if not url and not text:
            return []
            
        platforms = []
        social_patterns = {
            "twitter": [r"twitter\.com/([A-Za-z0-9_]+)", r"@([A-Za-z0-9_]+)"],
            "github": [r"github\.com/([A-Za-z0-9_-]+)"],
            "linkedin": [r"linkedin\.com/in/([A-Za-z0-9-]+)"],
            "instagram": [r"instagram\.com/([A-Za-z0-9_.]+)"]
        }
        
        combined_text = f"{url} {text}"
        
        for platform, patterns in social_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, combined_text, re.IGNORECASE)
                for match in matches:
                    if match and len(match) > 1:  # Filtrar matches válidos
                        platforms.append((platform, match))
        
        return platforms