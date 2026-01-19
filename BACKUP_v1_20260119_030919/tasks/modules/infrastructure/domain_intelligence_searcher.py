# services/worker/tasks/modules/infrastructure/domain_intelligence_searcher.py

import requests
import re
import time
from typing import Dict, List, Any, Optional
from ..base.base_searcher import BaseSearcher
from datetime import datetime
import json

class DomainIntelligenceSearcher(BaseSearcher):
    """Domain Intelligence Searcher - Información de dominios, subdomios y certificados"""
    
    def __init__(self):
        super().__init__()
        self.crt_sh = "https://crt.sh"
        self.virustotal_api = "https://www.virustotal.com/api/v3"
    
    def get_supported_types(self) -> List[str]:
        return ["domain", "email"]
    
    def get_priority(self) -> int:
        return 7
    
    def search(self, query: str, search_type: str, options: Dict = None) -> Dict[str, Any]:
        """
        Búsqueda de inteligencia de dominios (subdomios, certificados SSL, etc)
        """
        try:
            options = options or {}
            self.logger.info(f"Inteligencia de dominios: {query} (tipo: {search_type})")
            
            findings = []
            
            if search_type == "domain":
                findings = self._search_domain_intelligence(query)
            elif search_type == "email":
                # Extraer dominio del email
                if '@' in query:
                    domain = query.split('@')[1]
                    findings = self._search_domain_intelligence(domain)
            else:
                findings = self._search_domain_intelligence(query)
            
            return {
                "module": "domain_intelligence_searcher",
                "query": query,
                "search_type": search_type,
                "findings": findings,
                "timestamp": datetime.now().isoformat(),
                "success": len(findings) > 0
            }
        except Exception as e:
            self.logger.error(f"Error en búsqueda de inteligencia: {e}")
            return {
                "module": "domain_intelligence_searcher",
                "query": query,
                "search_type": search_type,
                "findings": [],
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "success": False
            }
    
    def _search_domain_intelligence(self, domain: str) -> List[Dict[str, Any]]:
        """Búsqueda completa de inteligencia de dominio"""
        findings = []
        
        # Limpiar dominio
        domain = domain.lower().strip()
        if domain.startswith('http://'):
            domain = domain[7:]
        if domain.startswith('https://'):
            domain = domain[8:]
        if '/' in domain:
            domain = domain.split('/')[0]
        
        try:
            # Certificados SSL/TLS via crt.sh
            findings.extend(self._get_ssl_certificates(domain))
            
            # Subdomios
            findings.extend(self._get_subdomains(domain))
            
            # Related domains
            findings.extend(self._get_related_domains(domain))
        
        except Exception as e:
            self.logger.debug(f"Error en búsqueda de dominio: {e}")
        
        return findings
    
    def _get_ssl_certificates(self, domain: str) -> List[Dict[str, Any]]:
        """Obtener certificados SSL/TLS del dominio"""
        certificates = []
        
        try:
            # Usar crt.sh para obtener certificados
            url = f"{self.crt_sh}/?q={domain}&output=json"
            
            time.sleep(1)
            response = self._make_request(url)
            
            if response.status_code == 200:
                try:
                    certs = response.json()
                    
                    # Agrupar por nombre único
                    seen_certs = set()
                    
                    for cert in certs:
                        cert_id = cert.get('id')
                        name_value = cert.get('name_value', '')
                        not_before = cert.get('not_before', '')
                        not_after = cert.get('not_after', '')
                        issuer_ca_id = cert.get('issuer_ca_id')
                        
                        # Procesar todos los nombres del certificado
                        for name in name_value.split('\n'):
                            name = name.strip()
                            if name and name not in seen_certs:
                                seen_certs.add(name)
                                
                                is_wildcard = name.startswith('*.')
                                cert_domain = name[2:] if is_wildcard else name
                                
                                certificate = {
                                    "type": "ssl_certificate",
                                    "domain": domain,
                                    "certificate_domain": name,
                                    "is_wildcard": is_wildcard,
                                    "certificate_id": cert_id,
                                    "not_before": not_before,
                                    "not_after": not_after,
                                    "issuer_ca_id": issuer_ca_id,
                                    "source": "crt.sh",
                                    "confidence": 0.95,
                                    "url": f"https://crt.sh/?id={cert_id}"
                                }
                                
                                # Si es un subdominio, marcarlo
                                if name != domain and not is_wildcard:
                                    certificate["type"] = "discovered_subdomain"
                                
                                certificates.append(certificate)
                
                except json.JSONDecodeError:
                    self.logger.debug("No valid JSON from crt.sh")
        
        except Exception as e:
            self.logger.debug(f"Error obteniendo certificados SSL: {e}")
        
        return certificates
    
    def _get_subdomains(self, domain: str) -> List[Dict[str, Any]]:
        """Obtener subdomios conocidos"""
        subdomains = []
        
        try:
            # Usar crt.sh sin formato JSON para contar
            url = f"{self.crt_sh}/?q=%.{domain}"
            
            time.sleep(1)
            response = self._make_request(url)
            
            if response.status_code == 200:
                # Extraer subdomios de la respuesta HTML
                pattern = r'<td[^>]*>([a-zA-Z0-9\-\.]+\.{}\b)'.format(re.escape(domain))
                found_subdomains = re.findall(pattern, response.text, re.IGNORECASE)
                
                for subdomain in set(found_subdomains):
                    subdomains.append({
                        "type": "discovered_subdomain",
                        "domain": domain,
                        "subdomain": subdomain,
                        "source": "crt.sh",
                        "confidence": 0.85
                    })
        
        except Exception as e:
            self.logger.debug(f"Error obteniendo subdomios: {e}")
        
        return subdomains
    
    def _get_related_domains(self, domain: str) -> List[Dict[str, Any]]:
        """Obtener dominios relacionados / typosquatting"""
        related = []
        
        try:
            # Usar API de SecurityTrails (requiere API key)
            # Para demostración, usamos enfoque alternativo
            
            # Géneros potenciales (común en typosquatting)
            domain_parts = domain.split('.')
            
            if len(domain_parts) >= 2:
                main_domain = domain_parts[0]
                tld = '.'.join(domain_parts[1:])
                
                # TLDs comunes
                common_tlds = ['com', 'org', 'net', 'io', 'co', 'uk', 'de', 'fr']
                
                # Variaciones comunes de typosquatting
                variations = [
                    main_domain + '1.' + tld,  # Número
                    main_domain + 's.' + tld,  # Plural
                    'www' + main_domain + '.' + tld,  # www prefix
                ]
                
                for variation in variations:
                    try:
                        # Intentar resolver
                        import socket
                        socket.gethostbyname(variation)
                        
                        related.append({
                            "type": "related_domain",
                            "original_domain": domain,
                            "related_domain": variation,
                            "suspicious": True,
                            "source": "dns_enumeration",
                            "confidence": 0.7
                        })
                    except:
                        pass
        
        except Exception as e:
            self.logger.debug(f"Error buscando dominios relacionados: {e}")
        
        return related
