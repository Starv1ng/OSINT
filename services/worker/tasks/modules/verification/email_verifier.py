# services/worker/tasks/modules/verification/email_verifier.py

import requests
from typing import Dict, List, Any
from ..base.base_searcher import BaseSearcher
import hashlib

class EmailVerifier(BaseSearcher):
    
    def search(self, query: str, search_type: str, options: Dict = None) -> Dict[str, Any]:
        """Verificar email en bases de datos de breaches"""
        try:
            self.logger.info(f"Verificando correo electrónico: {query}")
            
            if search_type != "email":
                return {
                    "error": "Este módulo solo soporta búsquedas de tipo 'email'",
                    "findings": []
                }
            
            # Verificar en Have I Been Pwned (API pública)
            breach_data = self._check_hibp(query)
            
            # Verificar formato y dominio
            validation_data = self._validate_email(query)
            
            findings = self._compile_findings(query, breach_data, validation_data)
            
            return {
                "email": query,
                "breach_check": breach_data,
                "validation": validation_data,
                "findings": findings,
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "sources_checked": ["Have I Been Pwned"]
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error en email verification: {e}")
            return {
                "error": str(e),
                "findings": []
            }
    
    def get_supported_types(self) -> List[str]:
        return ["email"]
    
    def get_priority(self) -> int:
        return 2
    
    def _check_hibp(self, email: str) -> Dict:
        """Consultar Have I Been Pwned API"""
        try:
            # Hash del email para privacidad
            email_hash = hashlib.sha1(email.lower().encode()).hexdigest().upper()
            prefix, suffix = email_hash[:5], email_hash[5:]
            
            url = f"https://api.pwnedpasswords.com/range/{prefix}"
            response = self._make_request(url)
            
            # Buscar el hash completo en la respuesta
            breaches = []
            for line in response.text.splitlines():
                hash_suffix, count = line.split(':')
                if hash_suffix == suffix:
                    breaches.append({
                        "breach_count": int(count),
                        "message": f"Email encontrado en {count} breaches conocidas"
                    })
                    break
            
            return {
                "breaches_found": len(breaches) > 0,
                "breach_details": breaches,
                "source": "Have I Been Pwned"
            }
            
        except Exception as e:
            return {
                "breaches_found": False,
                "error": str(e),
                "source": "Have I Been Pwned"
            }
    
    def _validate_email(self, email: str) -> Dict:
        """Validar formato y dominio del email"""
        import re
        import dns.resolver
        
        # Validar formato
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        is_valid_format = bool(re.match(pattern, email))
        
        # Validar dominio
        domain = email.split('@')[1] if '@' in email else ""
        has_mx_record = False
        
        try:
            if domain:
                dns.resolver.resolve(domain, 'MX')
                has_mx_record = True
        except:
            has_mx_record = False
        
        return {
            "valid_format": is_valid_format,
            "domain": domain,
            "has_mx_record": has_mx_record,
            "is_likely_valid": is_valid_format and has_mx_record
        }
    
    def _compile_findings(self, email: str, breach_data: Dict, validation_data: Dict) -> List[Dict]:
        """Compilar descubrimientos"""
        findings = []
        
        # Finding de brechas
        if breach_data.get("breaches_found"):
            findings.append({
                "type": "security_breach",
                "value": f"Email comprometido en {breach_data['breach_details'][0]['breach_count']} breaches",
                "source": "email_verifier",
                "confidence": 0.9,
                "context": f"Email {email} aparece en bases de datos de brechas",
                "metadata": {
                    "breach_count": breach_data['breach_details'][0]['breach_count'],
                    "email": email
                }
            })
        
        # Finding de validación
        if not validation_data.get("is_likely_valid"):
            findings.append({
                "type": "email_validation",
                "value": "Email con formato o dominio sospechoso",
                "source": "email_verifier", 
                "confidence": 0.7,
                "context": f"Problemas de validación con {email}",
                "metadata": {
                    "valid_format": validation_data.get("valid_format", False),
                    "has_mx_record": validation_data.get("has_mx_record", False),
                    "email": email
                }
            })
        
        return findings