# services/worker/tasks/modules/security/breach_searcher.py

import requests
import hashlib
import time
from typing import Dict, List, Any, Optional
from ..base.base_searcher import BaseSearcher
from datetime import datetime

class BreachSearcher(BaseSearcher):
    """Breach Database Searcher - Búsqueda en bases de datos de brechas"""
    
    def __init__(self):
        super().__init__()
        # HaveIBeenPwned API
        self.hibp_api = "https://haveibeenpwned.com/api/v3"
        self.session.headers.update({
            'User-Agent': 'OSINT-Bot/1.0',
            'Accept': 'application/json'
        })
    
    def get_supported_types(self) -> List[str]:
        return ["email", "username", "phone"]
    
    def get_priority(self) -> int:
        return 9
    
    def search(self, query: str, search_type: str, options: Dict = None) -> Dict[str, Any]:
        """
        Búsqueda en bases de datos de brechas de seguridad
        """
        try:
            self.logger.info(f"Búsqueda en bases de datos de brechas: {query} (tipo: {search_type})")
            
            findings = []
            
            if search_type == "email":
                findings = self._search_email_breach(query)
            elif search_type == "username":
                findings = self._search_username_breach(query)
            else:
                findings = self._search_email_breach(query)
            
            return {
                "module": "breach_searcher",
                "query": query,
                "search_type": search_type,
                "findings": findings,
                "timestamp": datetime.now().isoformat(),
                "success": len(findings) > 0
            }
        except Exception as e:
            self.logger.error(f"Error en búsqueda de brechas: {e}")
            return {
                "module": "breach_searcher",
                "query": query,
                "search_type": search_type,
                "findings": [],
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "success": False
            }
    
    def _search_email_breach(self, email: str) -> List[Dict[str, Any]]:
        """Buscar si email está en bases de brechas"""
        findings = []
        
        try:
            # HaveIBeenPwned API (gratis, sin API key)
            url = f"{self.hibp_api}/breachedaccount/{email}"
            
            time.sleep(1.5)  # Rate limiting (1.5 requests/segundo máximo)
            
            try:
                response = self._make_request(url, timeout=10)
                
                if response.status_code == 200:
                    # Email encontrado en brechas
                    breaches = response.json()
                    for breach in breaches:
                        finding = {
                            "type": "email_breach",
                            "email": email,
                            "breach_name": breach.get('Name'),
                            "breach_title": breach.get('Title'),
                            "breach_date": breach.get('BreachDate'),
                            "add_date": breach.get('AddedDate'),
                            "data_classes": breach.get('DataClasses', []),
                            "is_verified": breach.get('IsVerified'),
                            "is_retired": breach.get('IsRetired'),
                            "url": breach.get('Url'),
                            "source": "haveibeenpwned",
                            "confidence": 0.99,
                            "severity": "high"
                        }
                        findings.append(finding)
                
                elif response.status_code == 404:
                    # El correo no está en brechas conocidas
                    self.logger.info(f"Correo {email} no encontrado en brechas conocidas")
                
            except requests.exceptions.RequestException as e:
                if '404' in str(e):
                    pass  # Normal si no hay brechas
                else:
                    raise
            
            # Búsqueda en Pastes
            pastes = self._search_email_pastes(email)
            findings.extend(pastes)
        
        except Exception as e:
            self.logger.debug(f"Error buscando email en brechas: {e}")
        
        return findings
    
    def _search_email_pastes(self, email: str) -> List[Dict[str, Any]]:
        """Buscar email en pastes públicas"""
        findings = []
        
        try:
            url = f"{self.hibp_api}/pasteaccount/{email}"
            
            time.sleep(1.5)
            
            try:
                response = self._make_request(url, timeout=10)
                
                if response.status_code == 200:
                    pastes = response.json()
                    for paste in pastes:
                        finding = {
                            "type": "email_paste",
                            "email": email,
                            "source_name": paste.get('Source'),
                            "title": paste.get('Title'),
                            "paste_date": paste.get('Date'),
                            "url": paste.get('Link'),
                            "data_count": paste.get('EmailCount'),
                            "source": "haveibeenpwned_pastes",
                            "confidence": 0.85,
                            "severity": "medium"
                        }
                        findings.append(finding)
            
            except requests.exceptions.RequestException as e:
                if '404' in str(e):
                    pass  # Normal si no hay pastes
                else:
                    raise
        
        except Exception as e:
            self.logger.debug(f"Error buscando pastes: {e}")
        
        return findings
    
    def _search_username_breach(self, username: str) -> List[Dict[str, Any]]:
        """Buscar username en brechas (búsqueda limitada)"""
        findings = []
        
        try:
            # Búsqueda en bases de datos públicas de usernames
            # UserSearch API (alternativa a HIBP para usernames)
            url = f"https://www.usersearch.org/includes/results.php?username={username}"
            
            time.sleep(2)
            response = self._make_request(url, timeout=10)
            
            if response.status_code == 200:
                # Análisis básico de respuesta
                if len(response.text) > 100:
                    finding = {
                        "type": "username_search",
                        "username": username,
                        "found": True,
                        "source": "user_search_public",
                        "url": url,
                        "confidence": 0.5,
                        "note": "Usuario potencialmente registrado en servicios públicos"
                    }
                    findings.append(finding)
        
        except Exception as e:
            self.logger.debug(f"Error buscando username: {e}")
        
        return findings
    
    def _check_password_hash(self, password: str) -> Optional[Dict[str, Any]]:
        """Verificar si una contraseña ha sido comprometida (k-anonymity)"""
        try:
            # HIBP Passwords API (k-anonymity approach)
            sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
            prefix = sha1[:5]
            suffix = sha1[5:]
            
            url = f"https://api.pwnedpasswords.com/range/{prefix}"
            
            time.sleep(1)
            response = self._make_request(url)
            
            if response.status_code == 200:
                # Buscar el suffix en la respuesta
                for line in response.text.split('\r\n'):
                    hash_suffix, count = line.split(':')
                    if hash_suffix == suffix:
                        return {
                            "type": "password_compromised",
                            "compromised_count": int(count),
                            "severity": "critical",
                            "source": "haveibeenpwned_passwords",
                            "confidence": 0.99,
                            "note": f"Contraseña encontrada {count} veces en brechas"
                        }
        
        except Exception as e:
            self.logger.debug(f"Error verificando contraseña: {e}")
        
        return None
