# services/worker/tasks/dynamic_orchestrator.py

import asyncio
import re
import logging
import os
from typing import Dict, List, Any, Set, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from collections import defaultdict

# Importar módulos reales
from .modules.web.web_spider import WebSpider
from .modules.verification.email_verifier import EmailVerifier
from .modules.social_media.twitter_searcher import TwitterSearcher
from .modules.social_media.linkedin_searcher import LinkedInSearcher
from .modules.search_engine.search_engine_searcher import SearchEngineSearcher
from .modules.web.selective_crawler import SelectiveCrawler
from .modules.development.github_searcher import GitHubSearcher
from .modules.infrastructure.dns_whois_searcher import DNSWhoisSearcher
from .modules.infrastructure.domain_intelligence_searcher import DomainIntelligenceSearcher
from .modules.security.breach_searcher import BreachSearcher

# Importar analizador inteligente de input
from .modules.utils.input_analyzer import InputAnalyzer

from .es_client import index_findings, index_module_run

logger = logging.getLogger(__name__)


class DynamicModuleOrchestrator:
    """Orquestador dinámico que ejecuta módulos iterativamente basado en hallazgos"""
    
    def __init__(
        self,
        max_workers: int = 3,
        max_iterations: int = 5,
        relevance_threshold: float = 0.5,
        execution_mode: str = None,
        pg_client=None,
    ):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.max_iterations = max_iterations
        self.relevance_threshold = relevance_threshold
        self.execution_mode = execution_mode or 'normal'
        self.pg_client = pg_client
        
        # Aplicar preajuste si se especifica modo
        if execution_mode and execution_mode != 'custom':
            try:
                from ..config.dynamic_search_config import EXECUTION_MODES
                if execution_mode in EXECUTION_MODES:
                    config = EXECUTION_MODES[execution_mode]
                    self.max_iterations = config.get('max_iterations', self.max_iterations)
                    self.relevance_threshold = config.get('relevance_threshold', self.relevance_threshold)
                    self.max_workers = config.get('max_workers', self.max_workers)
                    logger.info(f"Modo: {execution_mode} - Iteraciones: {self.max_iterations}, Trabajadores: {self.max_workers}")
            except:
                pass
        
        # Inicializar módulos reales
        self.modules = {
            "search": SearchEngineSearcher(),
            "webspider": WebSpider(),
            "twitter": TwitterSearcher(),
            "linkedin": LinkedInSearcher(),
            "github": GitHubSearcher(),
            "dns_whois": DNSWhoisSearcher(),
            "domain_intelligence": DomainIntelligenceSearcher(),
            "breach": BreachSearcher(),
            "email_verifier": EmailVerifier(),
            "selective_crawler": SelectiveCrawler(),
        }

        try:
            from .modules.mei.email_extractor import EmailExtractorMEI
            from .modules.mei.phone_extractor import PhoneExtractorMEI
            from .modules.mei.username_extractor import UsernameExtractorMEI
            from .modules.mei.image_extractor import ImageExtractorMEI
            
            self.modules.update({
                'mei_email': EmailExtractorMEI(),
                'mei_phone': PhoneExtractorMEI(),
                'mei_username': UsernameExtractorMEI(),
                'mei_image': ImageExtractorMEI(),
            })
        except Exception:
            logger.debug("MEI modules no disponibles")

        # Mapeo de tipos de indicadores a módulos que los procesan
        self.indicator_module_mapping = {
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

        logger.info(f"DynamicModuleOrchestrator inicializado (modo: {self.execution_mode})")

    async def execute_dynamic_search(self, job_id: str, search_data: Dict) -> Dict[str, Any]:
        """Ejecutar búsqueda dinámica con iteraciones"""
        initial_query = search_data.get("value", "")
        initial_type = search_data.get("input_type", "general")
        
        logger.info(f"Búsqueda dinámica iniciada: '{initial_query}' (tipo: {initial_type})")
        
        # Inicializar estado
        all_findings = []
        processed_indicators = set()  # Para evitar re-procesar
        iteration = 0
        new_indicators_found = True
        
        # Ejecutar iteraciones mientras haya indicadores nuevos
        while iteration < self.max_iterations and new_indicators_found:
            iteration += 1
            
            # Check for pause status before each iteration
            try:
                if self.pg_client is None:
                    from shared.postgres_client import PostgreSQLClient
                    db_url = os.environ.get("DATABASE_URL", "postgresql://dev:devpass@postgres:5432/osint")
                    self.pg_client = PostgreSQLClient(db_url)

                with self.pg_client.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT status FROM jobs WHERE job_id = %s", (job_id,))
                        result = cur.fetchone()
                        if result and result[0] == 'paused':
                            logger.info(f"Job {job_id} has been paused, stopping execution")
                            return {
                                "search_query": initial_query,
                                "search_type": initial_type,
                                "findings": all_findings,
                                "status": "paused",
                                "iterations": iteration - 1
                            }
            except Exception as pause_check_error:
                logger.warning(f"Could not check pause status: {pause_check_error}")
            
            logger.info(f"\nIteración {iteration}/{self.max_iterations}")
            
            iteration_findings = []
            
            if iteration == 1:
                # Primera iteración: usar búsqueda inicial
                iteration_findings = await self._execute_initial_search(
                    job_id, initial_query, initial_type, search_data
                )
            else:
                # Iteraciones posteriores: procesar nuevos indicadores
                new_indicators = self._extract_new_indicators(
                    all_findings, processed_indicators
                )
                
                if not new_indicators:
                    logger.info("   ℹ️  No hay nuevos indicadores para procesar")
                    new_indicators_found = False
                    break
                
                logger.info(f"Procesando {len(new_indicators)} nuevos indicadores")
                iteration_findings = await self._process_indicators_dynamically(
                    job_id, new_indicators, search_data
                )
                
                # Marcar indicadores como procesados
                for indicator_type, indicators in new_indicators.items():
                    processed_indicators.update(indicators)

            # Combinar resultados
            old_count = len(all_findings)
            all_findings.extend(iteration_findings)
            all_findings = self._deduplicate_findings(all_findings)
            
            new_findings = len(all_findings) - old_count
            logger.info(f"Iteración {iteration}: +{new_findings} hallazgos únicos")
            
            # Verificar si hay información relevante nueva
            if new_findings == 0:
                new_indicators_found = False
                logger.info("   ℹ️  Convergencia alcanzada - no hay información nueva relevante")

        # Resultado final
        return {
            "search_query": initial_query,
            "search_type": initial_type,
            "findings": all_findings,
            "iterations": iteration,
            "summary": {
                "total_findings": len(all_findings),
                "total_iterations": iteration,
                "timestamp": datetime.now().isoformat(),
                "converged": not new_indicators_found
            }
        }

    async def _execute_initial_search(self, job_id: str, query: str, search_type: str, search_data: Dict) -> List[Dict]:
        """Ejecutar búsqueda inicial"""
        findings = []
        
        # Seleccionar módulos iniciales según tipo (ahora con InputAnalyzer)
        initial_modules = self._select_initial_modules(search_type, query=query, search_data=search_data)
        logger.info(f"Módulos iniciales: {initial_modules}")
        
        # Ejecutar en paralelo
        tasks = []
        for module_name in initial_modules:
            if module_name in self.modules:
                module = self.modules[module_name]
                if module.is_enabled():
                    tasks.append(
                        self._execute_module(job_id, module, query, search_type, search_data)
                    )
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error: {result}")
                continue
            
            data = result.get('data') or {}
            if data.get('findings'):
                findings.extend(data['findings'])
        
        return findings

    async def _process_indicators_dynamically(self, job_id: str, new_indicators: Dict[str, Set[str]], search_data: Dict) -> List[Dict]:
        """Procesar nuevos indicadores dinámicamente"""
        findings = []
        tasks = []
        
        # Para cada tipo de indicador, ejecutar módulos correspondientes
        for indicator_type, indicators in new_indicators.items():
            if not indicators:
                continue
            
            module_names = self.indicator_module_mapping.get(indicator_type, [])
            
            for indicator_value in indicators:
                for module_name in module_names:
                    if module_name not in self.modules:
                        continue
                    
                    module = self.modules[module_name]
                    if not module.is_enabled():
                        continue
                    
                    # Crear tarea para este módulo + indicador
                    logger.info(f"      → {module_name} procesando {indicator_type}: {indicator_value[:50]}")
                    
                    tasks.append(
                        self._execute_module(
                            job_id, module, indicator_value, indicator_type, search_data
                        )
                    )
        
        # Ejecutar todas las tareas
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    continue
                
                data = result.get('data') or {}
                if data.get('findings'):
                    findings.extend(data['findings'])
        
        return findings

    def _select_initial_modules(self, search_type: str, query: str = None, search_data: Dict = None) -> List[str]:
        """
        Seleccionar módulos iniciales según tipo de búsqueda
        Ahora inteligente: analiza el input y selecciona módulos óptimos
        """
        # Si hay query y search_data, usar InputAnalyzer para selección inteligente
        if query and search_data:
            try:
                analysis = InputAnalyzer.analyze(query)
                input_type = analysis.get('input_type', 'unknown')
                primary_modules = analysis.get('primary_modules', [])
                
                if primary_modules:
                    # Mapear nombres de módulos del InputAnalyzer a nombres internos
                    module_mapping = {
                        'TwitterSearcher': 'twitter',
                        'LinkedInSearcher': 'linkedin',
                        'GitHubSearcher': 'github',
                        'SearchEngineSearcher': 'search',
                        'WebSpider': 'webspider',
                        'SelectiveCrawler': 'selective_crawler',
                        'DomainIntelligenceSearcher': 'domain_intelligence',
                        'DNSWhoisSearcher': 'dns_whois',
                        'EmailVerifier': 'email_verifier',
                        'BreachSearcher': 'breach',
                    }
                    
                    # Convertir nombres de módulos
                    selected_modules = []
                    for module_name in primary_modules:
                        internal_name = module_mapping.get(module_name)
                        if internal_name and internal_name in self.modules:
                            selected_modules.append(internal_name)
                    
                    if selected_modules:
                        logger.info(f"   🧠 InputAnalyzer detectó tipo: {input_type} (confidence: {analysis.get('confidence', 0):.2f})")
                        logger.info(f"Módulos seleccionados: {selected_modules}")
                        return selected_modules
            except Exception as e:
                logger.debug(f"   ⚠️  InputAnalyzer falló: {e}, usando estrategia fallback")
        
        # Fallback: estrategia clásica por tipo
        strategies = {
            "person": ["search", "webspider"],
            "email": ["search", "email_verifier"],
            "phone": ["search", "dns_whois"],
            "username": ["search", "twitter"],
            "company": ["search", "linkedin"],
            "domain": ["dns_whois", "domain_intelligence"],
            "general": ["search", "webspider"]
        }
        
        return strategies.get(search_type, ["search"])

    def _extract_new_indicators(self, all_findings: List[Dict], processed: Set[str]) -> Dict[str, Set[str]]:
        """Extraer nuevos indicadores de los hallazgos"""
        new_indicators = defaultdict(set)
        
        indicator_types = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'username': r'@([A-Za-z0-9_]{2,30})',
            'url': r'https?://[^\s"\'<>]+',
            'domain': r'(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}',
            'ip': r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
        }
        
        for finding in all_findings:
            if not isinstance(finding, dict):
                continue
            
            finding_type = finding.get('type', '')
            finding_value = finding.get('value', '')
            
            # Extraer indicadores por tipo explícito
            if finding_type == 'email' and finding_value:
                email = finding_value.strip()
                if email not in processed:
                    new_indicators['email'].add(email)
            
            elif finding_type in ['username', 'social_profile']:
                username = finding_value.strip()
                if username and username not in processed:
                    new_indicators['username'].add(username)
            
            elif finding_type == 'url' or finding_type == 'link':
                url = finding_value.strip()
                if url.startswith('http') and url not in processed:
                    new_indicators['url'].add(url)
            
            elif finding_type == 'domain':
                domain = finding_value.strip()
                if domain not in processed:
                    new_indicators['domain'].add(domain)
            
            elif finding_type == 'ip' or finding_type == 'ip_info':
                ip = finding_value.strip()
                if ip and ip not in processed:
                    new_indicators['ip'].add(ip)
            
            # Extracción regex del valor del hallazgo
            value_text = str(finding.get('value', ''))
            
            for ind_type, pattern in indicator_types.items():
                matches = re.findall(pattern, value_text, re.IGNORECASE)
                for match in matches:
                    if ind_type == 'username':
                        match = match.lstrip('@')
                    
                    if match not in processed and match not in new_indicators[ind_type]:
                        # Validar que no sea valor duplicado conocido
                        new_indicators[ind_type].add(match)
        
        return dict(new_indicators)

    def _deduplicate_findings(self, findings: List[Dict]) -> List[Dict]:
        """Eliminar hallazgos duplicados"""
        seen = {}
        unique = []
        
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            
            key = (finding.get('type'), finding.get('value'))
            if key not in seen:
                seen[key] = True
                unique.append(finding)
        
        return unique

    async def _execute_module(self, job_id: str, module, query: str, search_type: str, search_data: Dict):
        """Ejecutar módulo individual"""
        try:
            module_name = module.__class__.__name__
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                module.search,
                query, search_type, search_data
            )
            
            try:
                module_run_id = index_module_run(job_id, module_name, result or {})
            except Exception as e:
                logger.debug(f"Error indexando en ES: {e}")
                module_run_id = None

            try:
                findings = (result or {}).get('findings') or []
                for f in findings:
                    if module_run_id:
                        f['module_run_id'] = module_run_id
                if findings:
                    index_findings(job_id, findings)
            except Exception as e:
                logger.debug(f"Error indexando findings: {e}")

            return {
                "module": module_name,
                "success": True,
                "data": result,
                "execution_time": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error en módulo: {e}")
            return {
                "module": module.__class__.__name__,
                "success": False,
                "error": str(e),
                "execution_time": datetime.now().isoformat()
            }
