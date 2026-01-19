# services/worker/tasks/modules/infrastructure/dns_whois_searcher.py

import dns.resolver
import dns.reversename
import requests
import re
import time
from typing import Dict, List, Any, Optional
from ..base.base_searcher import BaseSearcher
from datetime import datetime
import socket

class DNSWhoisSearcher(BaseSearcher):
    """DNS/WHOIS Searcher - Información de infraestructura de dominios"""
    
    def __init__(self):
        super().__init__()
        self.dns_resolver = dns.resolver.Resolver()
        self.dns_resolver.timeout = 5
        self.dns_resolver.lifetime = 10
    
    def get_supported_types(self) -> List[str]:
        return ["domain", "email", "phone", "ip"]
    
    def get_priority(self) -> int:
        return 6
    
    def search(self, query: str, search_type: str, options: Dict = None) -> Dict[str, Any]:
        """
        Búsqueda de información DNS, WHOIS e IP
        """
        try:
            self.logger.info(f"Búsqueda DNS/WHOIS: {query} (tipo: {search_type})")
            
            findings = []
            
            if search_type == "domain":
                findings = self._search_domain(query)
            elif search_type == "ip":
                findings = self._search_ip(query)
            elif search_type == "email":
                # Extraer dominio del email
                if '@' in query:
                    domain = query.split('@')[1]
                    findings = self._search_domain(domain)
            else:
                findings = self._search_domain(query)
            
            return {
                "module": "dns_whois_searcher",
                "query": query,
                "search_type": search_type,
                "findings": findings,
                "timestamp": datetime.now().isoformat(),
                "success": len(findings) > 0
            }
        except Exception as e:
            self.logger.error(f"Error en búsqueda DNS/WHOIS: {e}")
            return {
                "module": "dns_whois_searcher",
                "query": query,
                "search_type": search_type,
                "findings": [],
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "success": False
            }
    
    def _search_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Búsqueda de información DNS del dominio"""
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
            # A Records (IPv4)
            findings.extend(self._get_a_records(domain))
            
            # AAAA Records (IPv6)
            findings.extend(self._get_aaaa_records(domain))
            
            # MX Records
            findings.extend(self._get_mx_records(domain))
            
            # NS Records
            findings.extend(self._get_ns_records(domain))
            
            # TXT Records (SPF, DKIM, DMARC)
            findings.extend(self._get_txt_records(domain))
            
            # WHOIS Info
            whois_info = self._get_whois_info(domain)
            if whois_info:
                findings.append(whois_info)
            
            # SOA Record
            findings.extend(self._get_soa_records(domain))
        
        except Exception as e:
            self.logger.debug(f"Error en búsqueda DNS para {domain}: {e}")
        
        return findings
    
    def _get_a_records(self, domain: str) -> List[Dict[str, Any]]:
        """Obtener registros A"""
        records = []
        try:
            answers = self.dns_resolver.resolve(domain, 'A')
            for rdata in answers:
                records.append({
                    "type": "dns_a_record",
                    "domain": domain,
                    "record_type": "A",
                    "value": str(rdata),
                    "ip": str(rdata),
                    "source": "dns",
                    "confidence": 0.95
                })
        except Exception as e:
            self.logger.debug(f"Error obteniendo A records: {e}")
        return records
    
    def _get_aaaa_records(self, domain: str) -> List[Dict[str, Any]]:
        """Obtener registros AAAA (IPv6)"""
        records = []
        try:
            answers = self.dns_resolver.resolve(domain, 'AAAA')
            for rdata in answers:
                records.append({
                    "type": "dns_aaaa_record",
                    "domain": domain,
                    "record_type": "AAAA",
                    "value": str(rdata),
                    "ipv6": str(rdata),
                    "source": "dns",
                    "confidence": 0.95
                })
        except Exception:
            pass
        return records
    
    def _get_mx_records(self, domain: str) -> List[Dict[str, Any]]:
        """Obtener registros MX (servidores de correo)"""
        records = []
        try:
            answers = self.dns_resolver.resolve(domain, 'MX')
            for rdata in answers:
                records.append({
                    "type": "dns_mx_record",
                    "domain": domain,
                    "record_type": "MX",
                    "mail_server": str(rdata.exchange),
                    "preference": int(rdata.preference),
                    "source": "dns",
                    "confidence": 0.95
                })
        except Exception as e:
            self.logger.debug(f"Error obteniendo MX records: {e}")
        return records
    
    def _get_ns_records(self, domain: str) -> List[Dict[str, Any]]:
        """Obtener registros NS (nameservers)"""
        records = []
        try:
            answers = self.dns_resolver.resolve(domain, 'NS')
            for rdata in answers:
                records.append({
                    "type": "dns_ns_record",
                    "domain": domain,
                    "record_type": "NS",
                    "nameserver": str(rdata),
                    "source": "dns",
                    "confidence": 0.95
                })
        except Exception as e:
            self.logger.debug(f"Error obteniendo NS records: {e}")
        return records
    
    def _get_txt_records(self, domain: str) -> List[Dict[str, Any]]:
        """Obtener registros TXT (SPF, DKIM, DMARC, etc)"""
        records = []
        try:
            answers = self.dns_resolver.resolve(domain, 'TXT')
            for rdata in answers:
                value = str(rdata).strip('"')
                record_type = "spf" if value.startswith('v=spf1') else \
                             "dmarc" if domain.startswith('_dmarc.') else \
                             "dkim" if '_domainkey' in domain else "txt"
                records.append({
                    "type": "dns_txt_record",
                    "domain": domain,
                    "record_type": "TXT",
                    "subtype": record_type,
                    "value": value,
                    "source": "dns",
                    "confidence": 0.95
                })
        except Exception:
            pass
        return records
    
    def _get_soa_records(self, domain: str) -> List[Dict[str, Any]]:
        """Obtener registros SOA"""
        records = []
        try:
            answers = self.dns_resolver.resolve(domain, 'SOA')
            for rdata in answers:
                records.append({
                    "type": "dns_soa_record",
                    "domain": domain,
                    "record_type": "SOA",
                    "primary_ns": str(rdata.mname),
                    "responsible_party": str(rdata.rname),
                    "serial": str(rdata.serial),
                    "refresh": int(rdata.refresh),
                    "retry": int(rdata.retry),
                    "expire": int(rdata.expire),
                    "ttl": int(rdata.minimum),
                    "source": "dns",
                    "confidence": 0.95
                })
        except Exception as e:
            self.logger.debug(f"Error obteniendo SOA records: {e}")
        return records
    
    def _get_whois_info(self, domain: str) -> Optional[Dict[str, Any]]:
        """Obtener información WHOIS (aproximado vía APIs públicas)"""
        try:
            # Usar API pública de WHOIS
            url = f"https://www.whoisxmlapi.com/api/gateway?apiKey=at_free&domain={domain}"
            time.sleep(1)
            response = self._make_request(url)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('WhoisRecord', {})
                
                return {
                    "type": "whois_info",
                    "domain": domain,
                    "registrar": result.get('registrarName'),
                    "created_date": result.get('createdDate'),
                    "updated_date": result.get('updatedDate'),
                    "expires_date": result.get('expiresDate'),
                    "registrant_name": result.get('registrant', {}).get('name'),
                    "registrant_organization": result.get('registrant', {}).get('organization'),
                    "registrant_country": result.get('registrant', {}).get('country'),
                    "admin_name": result.get('administrativeContact', {}).get('name'),
                    "tech_name": result.get('technicalContact', {}).get('name'),
                    "source": "whois",
                    "confidence": 0.8
                }
        except Exception as e:
            self.logger.debug(f"Error obteniendo WHOIS: {e}")
        
        return None
    
    def _search_ip(self, ip: str) -> List[Dict[str, Any]]:
        """Búsqueda de información de IP (reverse DNS, geolocalización)"""
        findings = []
        
        try:
            # Reverse DNS
            try:
                reverse_dns = socket.gethostbyaddr(ip)
                findings.append({
                    "type": "reverse_dns",
                    "ip": ip,
                    "hostname": reverse_dns[0],
                    "aliases": reverse_dns[1],
                    "source": "dns",
                    "confidence": 0.9
                })
            except:
                pass
            
            # Información de IP (geolocalización, ASN, etc)
            ip_info = self._get_ip_info(ip)
            if ip_info:
                findings.append(ip_info)
        
        except Exception as e:
            self.logger.debug(f"Error en búsqueda de IP: {e}")
        
        return findings
    
    def _get_ip_info(self, ip: str) -> Optional[Dict[str, Any]]:
        """Obtener información de geolocalización de IP"""
        try:
            # Usar API pública de IP
            url = f"https://ipapi.co/{ip}/json/"
            time.sleep(1)
            response = self._make_request(url)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "type": "ip_info",
                    "ip": ip,
                    "organization": data.get('org'),
                    "country": data.get('country_name'),
                    "country_code": data.get('country_code'),
                    "region": data.get('region'),
                    "city": data.get('city'),
                    "postal": data.get('postal'),
                    "latitude": data.get('latitude'),
                    "longitude": data.get('longitude'),
                    "timezone": data.get('timezone'),
                    "isp": data.get('isp'),
                    "source": "ip_geolocation",
                    "confidence": 0.8
                }
        except Exception as e:
            self.logger.debug(f"Error obteniendo info de IP: {e}")
        
        return None
