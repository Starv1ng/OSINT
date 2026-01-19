# services/worker/tasks/orchestrator.py
import asyncio
import re
import logging
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Importar módulos reales
from .modules.web.web_spider import WebSpider
from .modules.verification.email_verifier import EmailVerifier
from .modules.social_media.twitter_searcher import TwitterSearcher
from .modules.social_media.linkedin_searcher import LinkedInSearcher
from .modules.search_engine.search_engine_searcher import SearchEngineSearcher
from .modules.web.selective_crawler import SelectiveCrawler
# Nuevos módulos
from .modules.development.github_searcher import GitHubSearcher
from .modules.infrastructure.dns_whois_searcher import DNSWhoisSearcher
from .modules.infrastructure.domain_intelligence_searcher import DomainIntelligenceSearcher
from .modules.security.breach_searcher import BreachSearcher
# MEI extractors
from .modules.mei.email_extractor import EmailExtractorMEI
from .modules.mei.phone_extractor import PhoneExtractorMEI
from .modules.mei.username_extractor import UsernameExtractorMEI
from .modules.mei.image_extractor import ImageExtractorMEI
from .es_client import index_findings, index_module_run

logger = logging.getLogger(__name__)

class ModuleOrchestrator:
    """Orquestador para módulos OSINT reales"""
    
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Inicializar módulos reales
        self.modules = {
            # Motores de búsqueda (recopiladores generales de contenido)
            "search": SearchEngineSearcher(),
            "webspider": WebSpider(),
            
            # Redes sociales (descubrimiento de perfiles)
            "twitter": TwitterSearcher(),
            "linkedin": LinkedInSearcher(),
            
            # Plataformas de desarrollo (repositorios de código y usuarios)
            "github": GitHubSearcher(),
            
            # Infraestructura y DNS
            "dns_whois": DNSWhoisSearcher(),
            "domain_intelligence": DomainIntelligenceSearcher(),
            
            # Seguridad y bases de datos de brechas
            "breach": BreachSearcher(),
            
            # Verificación de correo electrónico
            "email_verifier": EmailVerifier(),
            
            # Rastreo web
            "selective_crawler": SelectiveCrawler(),
        }

        # Registrar módulos MEI (extractores de indicadores)
        try:
            self.modules.update({
                'mei_email': EmailExtractorMEI(),
                'mei_phone': PhoneExtractorMEI(),
                'mei_username': UsernameExtractorMEI(),
                'mei_image': ImageExtractorMEI(),
            })
        except Exception:
            # Si algún import o inicialización falla, continuar sin módulos MEI
            logger.debug("Módulos MEI no disponibles o falló su inicialización")
        
        # Estrategias de búsqueda por tipo
        # Usar el módulo genérico 'search' para consultas amplias; los módulos especializados
        # (twitter, email_verifier, webspider) se ejecutan según corresponda posteriormente.
        self.search_strategies = {
            "person": ["search", "twitter", "linkedin", "github"],
            "email": ["search", "email_verifier", "twitter", "breach"],
            "phone": ["search", "dns_whois"],
            "username": ["search", "twitter", "linkedin", "github", "breach"],
            "company": ["search", "linkedin", "github"],
            "domain": ["dns_whois", "domain_intelligence"],
            "general": ["search", "breach"]
        }
        
        logger.info("ModuleOrchestrator inicializado con módulos reales")
    
    async def execute_search(self, job_id: str, search_data: Dict) -> Dict[str, Any]:
        """Ejecutar búsqueda con módulos reales"""
        search_type = search_data.get("input_type", "general")
        query = search_data.get("value", "")
        
        logger.info(f"Ejecutando búsqueda real: '{query}' (tipo: {search_type})")
        # Estrategia: 1) Ejecutar módulos MPG (propósito general) para recopilar HTML y hallazgos iniciales
        mpg_keys = ['search', 'webspider']
        mpg_modules = [self.modules[k] for k in mpg_keys if k in self.modules and self.modules[k].is_enabled()]

        if not mpg_modules:
            return self._create_error_result(f"No hay módulos MPG disponibles para tipo: {search_type}", search_data)

        logger.info(f"Ejecutando módulos MPG: {[m.__class__.__name__ for m in mpg_modules]}")

        # Run MPG modules in parallel
        # If the module is the search engine, ask it to validate profiles so
        # it can return normalized social_profile findings (twitter, etc.).
        mpg_tasks = []
        for m in mpg_modules:
            # Copy search_data into options; module.search expects (query, search_type, options)
            opts = dict(search_data or {})
            # Enable profile validation for search engine when doing person/general searches
            if isinstance(m, SearchEngineSearcher) and search_type in ["person", "general"]:
                opts['validate_profiles'] = True
            mpg_tasks.append(self._execute_module(job_id, m, query, search_type, opts))
        mpg_results = await asyncio.gather(*mpg_tasks, return_exceptions=True)

        # Collect raw_html and initial findings
        aggregated_findings = []
        raw_htmls = []
        modules_executed = []

        for res in mpg_results:
            if isinstance(res, Exception):
                continue
            modules_executed.append(res.get('module'))
            data = res.get('data') or {}
            # collect findings
            if data.get('findings'):
                aggregated_findings.extend(data.get('findings'))
            # collect raw_html if present
            if data.get('raw_html'):
                raw_htmls.append(data.get('raw_html'))
            # support web_spider raw_pages
            if data.get('raw_pages'):
                # raw_pages expected to be dict url->html
                for html in (data.get('raw_pages') or {}).values():
                    raw_htmls.append(html)

        # 2) Extract indicators (MEI). If MEI modules exist, call them; otherwise use internal extractor
        # Before extracting indicators, run a selective crawler to fetch only
        # relevant pages (social profiles, about pages, repos) discovered in
        # the MPG findings. Those raw_pages will be the input for MEI modules.
        sc = self.modules.get('selective_crawler')
        # build candidate list from aggregated_findings (links and social_profile)
        candidate_urls = []
        social_domains = ('twitter.com', 'instagram.com', 'facebook.com', 'linkedin.com', 'youtube.com', 'tiktok.com', 'github.com')

        social_candidates = []
        other_candidates = []

        for f in aggregated_findings:
            if not isinstance(f, dict):
                continue
            t = f.get('type')
            v = f.get('value')
            if not v or not isinstance(v, str):
                continue

            val = v.strip()
            # Resolve protocol-relative URLs
            if val.startswith('//'):
                val = 'https:' + val

            # Skip obvious internal/search-only paths (duckduckgo/html etc.)
            if val.startswith('/') or val.startswith('#'):
                continue

            # Only keep absolute URLs (with scheme)
            if not (val.startswith('http://') or val.startswith('https://')):
                continue

            # Prefer social domains
            low = val.lower()
            if any(d in low for d in social_domains):
                social_candidates.append(val)
            else:
                other_candidates.append(val)

        # Deduplicate while preserving order
        def _uniq(seq):
            seen = set()
            out = []
            for x in seq:
                if x not in seen:
                    seen.add(x)
                    out.append(x)
            return out

        social_candidates = _uniq(social_candidates)
        other_candidates = _uniq(other_candidates)

        # If we have social candidates, use them first; otherwise take top other links
        if social_candidates:
            candidate_urls = social_candidates[:30]
        else:
            # Exclude obvious news/listing domains that are low-value for profiles?
            blacklist = ('duckduckgo.com', 'google.com', 'bing.com', 'yahoo.com', 'wikipedia.org')
            filtered = [u for u in other_candidates if not any(b in u for b in blacklist)]
            candidate_urls = (filtered or other_candidates)[:30]

        if sc and sc.is_enabled() and candidate_urls:
            try:
                sc_res = await self._execute_module(job_id, sc, query, 'URL', {'candidates': candidate_urls, 'max_pages': 20})
                if sc_res and sc_res.get('data'):
                    sc_data = sc_res.get('data') or {}
                    # merge fetched raw pages into the raw_htmls list for MEI
                    for html in (sc_data.get('raw_pages') or {}).values():
                        raw_htmls.append(html)
                    # merge any findings (raw_page metadata)
                    if sc_data.get('findings'):
                        aggregated_findings.extend(sc_data.get('findings'))
                    modules_executed.append(sc_res.get('module'))
            except Exception as e:
                logger.debug(f"Selective crawler failed: {e}")

        mei_modules = [m for k, m in self.modules.items() if k.startswith('mei') and m.is_enabled()]
        indicators = { 'emails': set(), 'phones': set(), 'usernames': set(), 'images': set() }

        if mei_modules:
            # future: call MEI modules (not present currently)
            for mei in mei_modules:
                try:
                    mei_res = mei.search('\n'.join(raw_htmls), 'html', search_data)
                    # expect mei_res to return findings list
                    for f in mei_res.get('findings', []):
                        t = f.get('type')
                        v = f.get('value')
                        if t == 'email': indicators['emails'].add(v)
                        if t == 'phone': indicators['phones'].add(v)
                        if t == 'social_profile' or t == 'username': indicators['usernames'].add(v)
                        if t == 'image': indicators['images'].add(v)
                except Exception as e:
                    logger.debug(f"MEI module failed: {e}")
        else:
            # Basic extraction fallback
            text_blob = '\n'.join(raw_htmls)
            # emails
            for e in re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', text_blob):
                indicators['emails'].add(e)
            # phones (very permissive)
            for p in re.findall(r'(\+?\d[\d\-\.\s\(\)]{6,}\d)', text_blob):
                indicators['phones'].add(p.strip())
            # twitter-like usernames @username
            for u in re.findall(r'@([A-Za-z0-9_]{2,15})', text_blob):
                indicators['usernames'].add(u)
            # image urls
            for img in re.findall(r'https?://[^\s"\']+\.(?:png|jpg|jpeg|gif|bmp)', text_blob, re.IGNORECASE):
                indicators['images'].add(img)

        logger.info(f"   Indicadores extraídos: emails={len(indicators['emails'])}, phones={len(indicators['phones'])}, usernames={len(indicators['usernames'])}")

        # 3) Run MGE modules (specific purpose) using extracted indicators
        mge_keys = [k for k in self.modules.keys() if k not in mpg_keys]
        mge_modules = [self.modules[k] for k in mge_keys if self.modules[k].is_enabled()]

        mge_tasks = []
        # For simplicity, call each MGE module with indicators it supports
        for module in mge_modules:
            supported = module.get_supported_types() if hasattr(module, 'get_supported_types') else []
            # usernames
            if 'username' in supported or 'general' in supported:
                for uname in indicators['usernames']:
                    mge_tasks.append(self._execute_module(job_id, module, uname, 'username', search_data))
            # email
            if 'email' in supported:
                for email in indicators['emails']:
                    mge_tasks.append(self._execute_module(job_id, module, email, 'email', search_data))
            # phone
            if 'phone' in supported:
                for phone in indicators['phones']:
                    mge_tasks.append(self._execute_module(job_id, module, phone, 'phone', search_data))

        mge_results = []
        if mge_tasks:
            mge_results = await asyncio.gather(*mge_tasks, return_exceptions=True)

        # Combine MGE results into aggregated_findings
        for res in mge_results:
            if isinstance(res, Exception):
                continue
            data = res.get('data') or {}
            if data.get('findings'):
                aggregated_findings.extend(data.get('findings'))
            modules_executed.append(res.get('module'))

        # Final combine and dedupe
        combined = {
            'search_query': query,
            'search_type': search_type,
            'modules_executed': modules_executed,
            'findings': aggregated_findings,
            'raw_results': {},
            'summary': {
                'total_modules': len(modules_executed),
                'total_findings': len(aggregated_findings),
                'timestamp': datetime.now().isoformat()
            }
        }

        # Deduplicate findings
        combined['findings'] = self._deduplicate_findings(combined['findings'])
        combined['summary']['unique_findings'] = len(combined['findings'])

        # Reorder findings to prioritize social profiles / known social domains first
        try:
            combined['findings'] = self._prioritize_social_profiles(combined['findings'])
        except Exception:
            # Do not fail the whole search if prioritization has an issue
            pass

        logger.info(f"Búsqueda completada: {len(combined.get('findings', []))} descubrimientos")
        return combined
    
    def _select_modules(self, search_type: str) -> List:
        """Seleccionar módulos basado en el tipo de búsqueda"""
        module_names = self.search_strategies.get(search_type, ["google"])
        
        selected_modules = []
        for module_name in module_names:
            if module_name in self.modules:
                module = self.modules[module_name]
                if module.is_enabled():
                    selected_modules.append(module)
        
        # Ordenar por prioridad (menor número = mayor prioridad)
        selected_modules.sort(key=lambda x: x.get_priority())
        return selected_modules
    
    async def _execute_module(self, job_id: str, module, query: str, search_type: str, search_data: Dict):
        """Ejecutar un módulo individual"""
        try:
            module_name = module.__class__.__name__
            logger.info(f"   → Ejecutando: {module_name}")
            
            # Ejecutar en thread pool (para operaciones bloqueantes)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor, 
                module.search, 
                query, search_type, search_data
            )
            # Indexar el module_run completo (incluye raw_result / html si el módulo lo tiene)
            try:
                module_run_id = index_module_run(job_id, module_name, result or {})
            except Exception as e:
                logger.error(f"Error indexando ejecución de módulo en Elasticsearch para {module_name}: {e}")
                module_run_id = None

            # Indexar findings parciales/por bloque para durabilidad incremental
            try:
                findings = (result or {}).get('findings') or []
                # Attach module_run_id to each finding
                for f in findings:
                    if module_run_id:
                        f['module_run_id'] = module_run_id
                if findings:
                    index_findings(job_id, findings)
            except Exception as e:
                logger.error(f"Error indexando hallazgos en Elasticsearch para {module_name}: {e}")

            return {
                "module": module_name,
                "success": True,
                "data": result,
                "execution_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error en {module.__class__.__name__}: {e}")
            return {
                "module": module.__class__.__name__,
                "success": False,
                "error": str(e),
                "execution_time": datetime.now().isoformat()
            }
    
    def _combine_results(self, results: List, modules: List, search_data: Dict) -> Dict:
        """Combinar resultados de todos los módulos"""
        combined = {
            "search_query": search_data["value"],
            "search_type": search_data["input_type"],
            "modules_executed": [],
            "modules_successful": [],
            "modules_failed": [],
            "findings": [],
            "raw_results": {},
            "summary": {
                "total_modules": len(modules),
                "successful_modules": 0,
                "failed_modules": 0,
                "total_findings": 0,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        successful_modules = 0
        
        for result in results:
            if isinstance(result, Exception):
                continue
                
            module_name = result["module"]
            combined["modules_executed"].append(module_name)
            
            if result["success"]:
                successful_modules += 1
                combined["modules_successful"].append(module_name)
                combined["raw_results"][module_name] = result["data"]
                
                # Extraer y combinar descubrimientos
                module_data = result["data"]
                if module_data and "findings" in module_data:
                    combined["findings"].extend(module_data["findings"])
            else:
                combined["modules_failed"].append(module_name)
                combined["raw_results"][module_name] = {"error": result["error"]}
        
        # Actualizar summary
        combined["summary"]["successful_modules"] = successful_modules
        combined["summary"]["failed_modules"] = len(modules) - successful_modules
        combined["summary"]["total_findings"] = len(combined["findings"])
        combined["summary"]["success_rate"] = successful_modules / len(modules) if modules else 0
        
        # Eliminar duplicados en findings
        combined["findings"] = self._deduplicate_findings(combined["findings"])
        combined["summary"]["unique_findings"] = len(combined["findings"])
        
        return combined
    
    def _deduplicate_findings(self, findings: List[Dict]) -> List[Dict]:
        """Eliminar descubrimientos duplicados"""
        seen = set()
        unique_findings = []
        
        for finding in findings:
            # Crear clave única basada en tipo y valor
            key = f"{finding.get('type', 'unknown')}:{finding.get('value', 'unknown')}"
            
            if key not in seen:
                seen.add(key)
                unique_findings.append(finding)
        
        return unique_findings

    def _prioritize_social_profiles(self, findings: List[Dict]) -> List[Dict]:
        """Move social profiles and known social-domain links to the front of the list.

        This is a lightweight heuristic: it looks for findings with type 'social_profile'
        and/or values containing well-known social domains and puts them first while
        preserving relative order otherwise.
        """
        if not findings:
            return findings

        social_domains = ('twitter.com', 'instagram.com', 'facebook.com', 'linkedin.com', 'youtube.com', 'tiktok.com')
        social = []
        others = []
        for f in findings:
            v = (f.get('value') or '').lower()
            if f.get('type') == 'social_profile' or any(d in v for d in social_domains):
                social.append(f)
            else:
                others.append(f)

        # Return social-first, but keep internal ordering
        return social + others
    
    def _create_error_result(self, error_message: str, search_data: Dict) -> Dict:
        """Crear resultado de error"""
        return {
            "search_query": search_data["value"],
            "search_type": search_data["input_type"],
            "error": error_message,
            "findings": [],
            "summary": {
                "total_findings": 0,
                "error": True,
                "error_message": error_message,
                "timestamp": datetime.now().isoformat()
            }
        }