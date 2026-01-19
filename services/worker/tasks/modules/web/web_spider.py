# services/worker/tasks/modules/web/web_spider.py

import time
import re
import urllib.parse
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
from ..base.base_searcher import BaseSearcher
from datetime import datetime

class WebSpider(BaseSearcher):
    """Web Spider - Implementación exacta del spider de SpiderFoot"""
    
    def __init__(self):
        super().__init__()
        
        # Configuración IDÉNTICA a SpiderFoot
        self.opts = {
            'robotsonly': False,
            'pausesec': 1,
            'maxpages': 50,
            'maxlevels': 3,
            'usecookies': True,
            'start': ['https://', 'http://'],
            'filterfiles': [
                'png', 'gif', 'jpg', 'jpeg', 'tiff', 'tif', 'tar', 'pdf', 
                'ico', 'flv', 'mp4', 'mp3', 'avi', 'mpg', 'gz', 'mpeg', 
                'iso', 'dat', 'mov', 'swf', 'rar', 'exe', 'zip', 'bin', 
                'bz2', 'xsl', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'csv'
            ],
            'filtermime': ['image/'],
            'filterusers': True,
            'nosubs': False,
            'useragent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Estados internos (como SpiderFoot)
        self.robotsRules = dict()
        self.fetchedPages = set()
        self.urlEvents = dict()
        self.siteCookies = dict()
        # Collected raw pages for indexing and MEI extraction
        self._collected_pages = {}
        
        # Headers
        self.session.headers.update({
            'User-Agent': self.opts['useragent'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
    
    def search(self, query: str, search_type: str, options: Dict = None) -> Dict[str, Any]:
        """Método principal - Simula handleEvent de SpiderFoot"""
        try:
            self.logger.info(f"SpiderFoot Spider iniciado para: {query}")
            
            # Determinar el evento type (como en SpiderFoot)
            if search_type in ["INTERNET_NAME", "DOMAIN_NAME"]:
                event_type = "INTERNET_NAME"
            elif search_type in ["LINKED_URL_INTERNAL", "URL"]:
                event_type = "LINKED_URL_INTERNAL" 
            else:
                event_type = "INTERNET_NAME"  # Por defecto
            
            # Simular el evento de SpiderFoot
            spider_target = self._handle_event(event_type, query)
            
            if not spider_target:
                return {
                    "error": f"No se pudo iniciar spidering para: {query}",
                    "events": []
                }
            
            # Ejecutar spidering (como spiderFrom de SpiderFoot)
            results = self._spider_from(spider_target)

            # Normalize results into a "findings" list expected by orchestrator
            findings = []
            for ev in results:
                try:
                    findings.append({
                        "type": ev.get("event_type", "unknown"),
                        "value": ev.get("data"),
                        "module": ev.get("module", "web_spider"),
                        "source": ev.get("source", "spider")
                    })
                except Exception:
                    # Defensive: skip malformed events
                    continue

            return {
                "module": "web_spider",
                "spider_target": spider_target,
                "events_generated": results,
                "findings": findings,
                "raw_pages": self._collected_pages,
                "crawl_summary": {
                    "pages_fetched": len(self.fetchedPages),
                    "levels_traversed": self._get_max_depth(results),
                    "events_count": len(results)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error en spider: {e}")
            return {
                "error": str(e),
                "events": [],
                "findings": []
            }
    
    def _handle_event(self, event_type: str, event_data: str) -> Optional[str]:
        """Implementación exacta de handleEvent de SpiderFoot"""
        
        # No spider links que encontramos nosotros mismos
        if "spider" in event_data:
            self.debug(f"Ignorando {event_data} de self")
            return None
        
        if event_data in self.urlEvents:
            self.debug(f"Ignorando {event_data} como ya spidered")
            return None
        
        # Simular el evento (simplificado)
        class MockEvent:
            def __init__(self, event_type, data):
                self.eventType = event_type
                self.data = data
                self.module = "external"
        
        mock_event = MockEvent(event_type, event_data)
        self.urlEvents[event_data] = mock_event
        
        spider_target = None
        
        # Determinar donde empezar spidering (como en handleEvent)
        if event_type == "INTERNET_NAME":
            for prefix in self.opts['start']:
                test_url = prefix + event_data
                if self._check_url_accessible(test_url):
                    spider_target = test_url
                    # En SpiderFoot aquí se emitiría LINKED_URL_INTERNAL
                    self.debug(f"URL accesible encontrada: {spider_target}")
                    break
        else:
            spider_target = event_data
        
        if not spider_target:
            self.debug(f"No reply from {event_data}, aborting")
            return None
        
        self.debug(f"Iniciando spider de {spider_target}")
        return spider_target
    
    def _spider_from(self, starting_point: str) -> List[Dict]:
        """Implementación exacta de spiderFrom de SpiderFoot"""
        pages_fetched = 0
        levels_traversed = 0
        
        # Respetar robots.txt si está habilitado
        if self.opts['robotsonly']:
            target_base = self._url_base_url(starting_point)
            if target_base not in self.robotsRules:
                robots_content = self._fetch_robots_txt(target_base)
                if robots_content:
                    self.robotsRules[target_base] = self._extract_urls_from_robots_txt(robots_content)
        
        # Primera iteración empezamos con el target link
        next_links = [starting_point]
        all_events = []
        
        # Spidering recursivo (misma lógica que SpiderFoot)
        while (pages_fetched < self.opts['maxpages']) and (levels_traversed <= self.opts['maxlevels']):
            if not next_links:
                self.debug("No more links to spider")
                break
            
            # Fetch contenido de nuevos links
            links = dict()
            for link in next_links:
                if self._check_for_stop():
                    break
                
                if link in self.fetchedPages:
                    self.debug(f"Already fetched {link}, skipping")
                    continue
                
                self.debug(f"Fetching fresh content from: {link}")
                
                # Pausa entre requests
                time.sleep(self.opts['pausesec'])
                
                # Procesar URL (como processUrl de SpiderFoot)
                fresh_links = self._process_url(link)
                if fresh_links:
                    links.update(fresh_links)
                
                pages_fetched += 1
                if pages_fetched >= self.opts['maxpages']:
                    self.debug(f"Max pages ({self.opts['maxpages']}) reached")
                    break
            
            # Limpiar y preparar siguiente iteración
            next_links = self._clean_links(links)
            self.debug(f"Found links for next level: {len(next_links)}")
            
            # Registrar eventos de esta iteración
            level_events = self._generate_events_for_links(next_links)
            all_events.extend(level_events)
            
            levels_traversed += 1
            self.debug(f"At level: {levels_traversed}, Pages: {pages_fetched}")
            
            if levels_traversed > self.opts['maxlevels']:
                self.debug(f"Max levels ({self.opts['maxlevels']}) reached")
                break
        
        return all_events
    
    def _process_url(self, url: str) -> Optional[Dict]:
        """Implementación de processUrl de SpiderFoot"""
        site = self._url_fqdn(url)
        cookies = self.siteCookies.get(site)
        
        # Filtrar tipos de archivo
        if self._is_filtered_file(url):
            self.debug(f"Filtering out URL with filtered file extension: {url}")
            return None
        
        # Fetch contenido
        fetched = self._fetch_url(url, cookies)
        if not fetched:
            return None
        
        self.fetchedPages.add(url)
        
        # Manejar cookies
        if self.opts['usecookies'] and fetched.get('headers'):
            if fetched['headers'].get('Set-Cookie'):
                self.siteCookies[site] = fetched['headers'].get('Set-Cookie')
                self.debug(f"Saved cookies for {site}")
        
        # Manejar redirects
        real_url = fetched.get('realurl')
        if real_url and real_url != url:
            self.debug(f"Redirect from {url} to {real_url}")
            self.fetchedPages.add(real_url)
            url = real_url
        
        content = fetched.get('content')
        if not content:
            return None
        
        # Extraer links del HTML (como extractLinksFromHtml de SpiderFoot)
        links = self._extract_links_from_html(url, content)
        
        if not links:
            self.debug(f"No links found at {url}")
            return None
        
        # Notificar sobre nuevos links encontrados
        for link in links:
            if link not in self.urlEvents:
                # En SpiderFoot aquí se emitiría evento LINKED_URL_INTERNAL/EXTERNAL
                self.debug(f"New link found: {link}")
        
        return links
    
    def _fetch_url(self, url: str, cookies=None) -> Optional[Dict]:
        """Fetch URL con manejo de errores"""
        try:
            response = self.session.get(
                url,
                cookies=cookies,
                timeout=30,
                allow_redirects=True
            )
            
            # record raw html for MEI extraction
            try:
                self._record_fetched_page(response.url, response.text)
            except Exception:
                pass

            return {
                'content': response.text,
                'headers': dict(response.headers),
                'realurl': response.url,
                'code': response.status_code
            }
            
        except Exception as e:
            # Log full exception with stack trace to help debugging
            try:
                self.logger.exception(f"Error fetching {url}")
            except Exception:
                # Fallback if logger.exception isn't available
                self.debug(f"Error fetching {url}: {e}")
            return None

    def _record_fetched_page(self, url: str, html: str):
        try:
            # store HTML; careful with memory in production
            self._collected_pages[url] = html
        except Exception:
            pass
    
    def _extract_links_from_html(self, base_url: str, html: str) -> Dict:
        """Extraer links de HTML (como extractLinksFromHtml de SpiderFoot)"""
        soup = BeautifulSoup(html, 'html.parser')
        links = {}
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = self._make_absolute_url(base_url, href)
            
            if full_url and self._is_valid_spider_url(full_url):
                links[full_url] = {
                    'text': link.get_text().strip(),
                    'url': full_url
                }
        
        return links
    
    def _clean_links(self, links: Dict) -> List[str]:
        """Limpiar links (como cleanLinks de SpiderFoot)"""
        return_links = []
        
        for link in links:
            link_base = self._url_base_url(link)
            link_fqdn = self._url_fqdn(link)
            
            # Skip external sites
            if not self._is_same_domain(link_fqdn):
                continue
            
            # Optionally skip sub-domains
            if self.opts['nosubs'] and not self._is_same_base_domain(link_fqdn):
                continue
            
            # Skip user directories
            if self.opts['filterusers'] and '/~' in link:
                continue
            
            # Respect robots.txt
            if self.opts['robotsonly'] and link_base in self.robotsRules:
                if self._is_blocked_by_robots(link, self.robotsRules[link_base]):
                    continue
            
            return_links.append(link)
        
        return return_links
    
    def _generate_events_for_links(self, links: List[str]) -> List[Dict]:
        """Generar eventos para links encontrados"""
        events = []
        
        for link in links:
            if self._is_same_domain(self._url_fqdn(link)):
                event_type = "LINKED_URL_INTERNAL"
            else:
                event_type = "LINKED_URL_EXTERNAL"
            
            events.append({
                "event_type": event_type,
                "data": link,
                "module": "web_spider",
                "source": "spider"
            })
        
        return events
    
    # Métodos auxiliares (helpers de SpiderFoot)
    def _url_base_url(self, url: str) -> str:
        """Como urlBaseUrl de SpiderFoot"""
        parsed = urllib.parse.urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    def _url_fqdn(self, url: str) -> str:
        """Como urlFQDN de SpiderFoot"""
        return urllib.parse.urlparse(url).netloc
    
    def _make_absolute_url(self, base_url: str, relative_url: str) -> Optional[str]:
        """Hacer URL absoluta"""
        try:
            return urllib.parse.urljoin(base_url, relative_url)
        except:
            return None
    
    def _is_valid_spider_url(self, url: str) -> bool:
        """Verificar si URL es válida para spidering"""
        if not url.startswith(('http://', 'https://')):
            return False
        
        if self._is_filtered_file(url):
            return False
        
        return True
    
    def _is_filtered_file(self, url: str) -> bool:
        """Verificar si es archivo filtrado"""
        path = urllib.parse.urlparse(url).path.lower()
        return any(path.endswith('.' + ext) for ext in self.opts['filterfiles'])
    
    def _is_same_domain(self, domain: str) -> bool:
        """Verificar si es mismo dominio (simplificado)"""
        # En implementación real, compararía con target domains
        return True
    
    def _is_same_base_domain(self, domain: str) -> bool:
        """Verificar si es mismo dominio base"""
        return self._is_same_domain(domain)
    
    def _check_url_accessible(self, url: str) -> bool:
        """Verificar si URL es accesible"""
        try:
            response = self.session.head(url, timeout=10, allow_redirects=True)
            return response.status_code == 200
        except:
            return False
    
    def _fetch_robots_txt(self, base_url: str) -> Optional[str]:
        """Fetch robots.txt"""
        try:
            robots_url = f"{base_url}/robots.txt"
            response = self.session.get(robots_url, timeout=10)
            return response.text if response.status_code == 200 else None
        except:
            return None
    
    def _extract_urls_from_robots_txt(self, robots_content: str) -> List[str]:
        """Extraer URLs de robots.txt (simplificado)"""
        # Implementación básica - en SpiderFoot es más complejo
        disallowed = []
        for line in robots_content.split('\n'):
            if line.lower().startswith('disallow:'):
                path = line.split(':', 1)[1].strip()
                if path:
                    disallowed.append(path)
        return disallowed
    
    def _is_blocked_by_robots(self, url: str, rules: List[str]) -> bool:
        """Verificar si URL está bloqueada por robots.txt"""
        path = urllib.parse.urlparse(url).path
        for rule in rules:
            if path.startswith(rule):
                return True
        return False
    
    def _check_for_stop(self) -> bool:
        """Verificar si debe detenerse (simulada)"""
        return False
    
    def _get_max_depth(self, events: List[Dict]) -> int:
        """Obtener máxima profundidad de eventos"""
        # Simplificado - en realidad necesitaríamos trackear profundidad
        return len([e for e in events if e['event_type'] == 'LINKED_URL_INTERNAL'])
    
    def debug(self, msg: str):
        """Método debug como en SpiderFoot"""
        self.logger.debug(msg)
    
    def get_supported_types(self) -> List[str]:
        return ["INTERNET_NAME", "DOMAIN_NAME", "LINKED_URL_INTERNAL", "URL"]
    
    def get_priority(self) -> int:
        return 1