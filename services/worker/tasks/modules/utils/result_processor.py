# services/worker/tasks/modules/utils/result_processor.py

import re
from typing import List, Dict, Any, Set, Optional
from .result_filter import ResultFilter


class ResultProcessor:
    """Procesador avanzado de resultados OSINT para eliminar ruido y mejorar calidad"""
    
    @staticmethod
    def process_findings(findings: List[Dict[str, Any]], query: str = '', context: str = 'general') -> Dict[str, Any]:
        """
        Procesa hallazgos completos:
        1. Filtra ruido
        2. Extrae indicadores adicionales
        3. Deduplica
        4. Clasifica por relevancia
        5. Agrega contexto
        
        Args:
            findings: Lista de hallazgos
            query: Consulta original para contexto
            context: 'person', 'company', 'email', etc.
        
        Returns:
            Dict con findings procesados, indicadores extraídos, y estadísticas
        """
        
        # 1. FILTRAR
        filtered = ResultFilter.clean_findings(findings, query)
        
        # 2. EXTRAER INDICADORES
        extracted_indicators = ResultProcessor._extract_indicators_from_findings(filtered)
        
        # 3. DEDUPLICAR
        deduplicated = ResultFilter.deduplicate_findings(filtered)
        
        # 4. CLASIFICAR POR RELEVANCIA
        scored = ResultProcessor._score_findings(deduplicated, query, context)
        
        # 5. AGRUPAR
        grouped = ResultFilter.group_findings_by_type(scored)
        
        return {
            'processed_findings': scored,
            'grouped_by_type': grouped,
            'extracted_indicators': extracted_indicators,
            'statistics': {
                'original_count': len(findings),
                'after_filter': len(filtered),
                'after_dedup': len(deduplicated),
                'final_count': len(scored),
                'types_found': list(grouped.keys()),
                'indicators_extracted': {
                    'emails': len(extracted_indicators.get('emails', [])),
                    'usernames': len(extracted_indicators.get('usernames', [])),
                    'urls': len(extracted_indicators.get('urls', [])),
                    'phones': len(extracted_indicators.get('phones', [])),
                }
            }
        }
    
    @staticmethod
    def _extract_indicators_from_findings(findings: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        """Extrae indicadores (emails, usernames, URLs, etc.) de los hallazgos"""
        indicators = {
            'emails': set(),
            'usernames': set(),
            'urls': set(),
            'phones': set(),
            'domains': set(),
        }
        
        for finding in findings:
            # Del valor principal
            value = str(finding.get('value', ''))
            
            # Extraer emails del valor
            emails = ResultFilter.extract_emails(value)
            indicators['emails'].update(emails)
            
            # Extraer URLs del valor
            urls = ResultFilter.extract_urls(value)
            indicators['urls'].update(urls)
            
            # Extraer dominios de URLs
            for url in urls:
                domain = ResultProcessor._extract_domain(url)
                if domain:
                    indicators['domains'].add(domain)
            
            # Del tipo social_profile, extraer username
            if finding.get('type') == 'social_profile':
                username = ResultProcessor._extract_username_from_profile(value)
                if username:
                    indicators['usernames'].add(username)
            
            # Del metadata
            metadata = finding.get('metadata', {})
            if metadata.get('username'):
                indicators['usernames'].add(metadata['username'])
            if metadata.get('email'):
                indicators['emails'].add(metadata['email'])
            if metadata.get('phone'):
                indicators['phones'].add(metadata['phone'])
            
            # Extraer de contexto/description
            context = finding.get('context', '')
            if context:
                emails = ResultFilter.extract_emails(context)
                indicators['emails'].update(emails)
                usernames = ResultFilter.extract_usernames(context)
                indicators['usernames'].update(usernames)
        
        # Convertir sets a sorted lists
        return {
            'emails': sorted(list(indicators['emails'])),
            'usernames': sorted(list(indicators['usernames'])),
            'urls': sorted(list(indicators['urls'])),
            'phones': sorted(list(indicators['phones'])),
            'domains': sorted(list(indicators['domains'])),
        }
    
    @staticmethod
    def _extract_domain(url: str) -> Optional[str]:
        """Extrae el dominio de una URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain if domain else None
        except:
            return None
    
    @staticmethod
    def _extract_username_from_profile(profile_url: str) -> Optional[str]:
        """Extrae username de una URL de perfil social"""
        # Patrones comunes
        patterns = [
            r'twitter\.com/([a-z0-9_]+)',
            r'instagram\.com/([a-z0-9_.-]+)',
            r'github\.com/([a-z0-9-]+)',
            r'linkedin\.com/in/([a-z0-9-]+)',
            r'/(?:users?|profiles?|author)/([a-z0-9_-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, profile_url, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    @staticmethod
    def _score_findings(findings: List[Dict[str, Any]], query: str = '', context: str = 'general') -> List[Dict[str, Any]]:
        """
        Puntúa hallazgos por relevancia basado en:
        - Tipo de hallazgo
        - Coincidencia con query
        - Confianza reportada
        - Fuente
        """
        query_tokens = set(t.lower() for t in query.split() if len(t) > 2)
        
        scored_findings = []
        for finding in findings:
            score = 0.5  # Base score
            
            # Puntuación por tipo
            finding_type = finding.get('type', '').lower()
            type_scores = {
                'social_profile': 1.0,
                'email': 0.9,
                'phone': 0.85,
                'username': 0.8,
                'raw_page': 0.6,
                'url': 0.5,
                'link': 0.4,
            }
            score = type_scores.get(finding_type, 0.5)
            
            # Bonus por confianza reportada
            confidence = finding.get('confidence', 0)
            score += (confidence * 0.3)
            
            # Bonus por coincidencia con query
            value = str(finding.get('value', '')).lower()
            for token in query_tokens:
                if token in value:
                    score += 0.1
            
            # Bonus por fuente verificada
            source = finding.get('source', '').lower()
            if 'verified' in source or 'validated' in source:
                score += 0.15
            
            # Capear a máximo 1.0
            score = min(score, 1.0)
            
            # Agregar score al finding
            finding_with_score = dict(finding)
            finding_with_score['relevance_score'] = round(score, 2)
            scored_findings.append(finding_with_score)
        
        # Ordenar por score descendente
        scored_findings.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return scored_findings
    
    @staticmethod
    def get_high_confidence_findings(findings: List[Dict[str, Any]], min_confidence: float = 0.7) -> List[Dict[str, Any]]:
        """Filtra hallazgos por confianza mínima"""
        return [f for f in findings if f.get('relevance_score', 0) >= min_confidence]
    
    @staticmethod
    def format_for_display(processed: Dict[str, Any], query: str = '') -> str:
        """Formatea resultados procesados para mostrar al usuario"""
        output = []
        
        # Header
        output.append(f"\n{'='*60}")
        output.append(f"Resultados OSINT para: {query}")
        output.append(f"{'='*60}\n")
        
        # Estadísticas
        stats = processed.get('statistics', {})
        output.append(f"Estadísticas:")
        output.append(f"  • Hallazgos originales: {stats.get('original_count', 0)}")
        output.append(f"  • Tras filtrado: {stats.get('after_filter', 0)}")
        output.append(f"  • Resultados finales: {stats.get('final_count', 0)}")
        output.append(f"  • Reducción: {100 - (stats.get('final_count', 0) * 100 // max(stats.get('original_count', 1), 1))}%\n")
        
        # Indicadores extraídos
        indicators = processed.get('extracted_indicators', {})
        if any(indicators.values()):
            output.append(f"Indicadores extraídos:")
            if indicators.get('emails'):
                output.append(f"  Correos electrónicos ({len(indicators['emails'])}):")
                for email in indicators['emails'][:10]:
                    output.append(f"      - {email}")
                if len(indicators['emails']) > 10:
                    output.append(f"      ... y {len(indicators['emails']) - 10} más")
            if indicators.get('usernames'):
                output.append(f"  Nombres de usuario ({len(indicators['usernames'])}):")
                for username in indicators['usernames'][:10]:
                    output.append(f"      - {username}")
                if len(indicators['usernames']) > 10:
                    output.append(f"      ... y {len(indicators['usernames']) - 10} más")
            if indicators.get('urls'):
                output.append(f"  URLs ({len(indicators['urls'])}):")
                for url in indicators['urls'][:5]:
                    output.append(f"      - {url}")
                if len(indicators['urls']) > 5:
                    output.append(f"      ... y {len(indicators['urls']) - 5} más")
            output.append("")
        
        # Hallazgos por tipo
        grouped = processed.get('grouped_by_type', {})
        if grouped:
            output.append(f"Hallazgos por tipo:")
            for ftype, findings_list in sorted(grouped.items()):
                output.append(f"  • {ftype.upper()} ({len(findings_list)}):")
                for finding in findings_list[:3]:
                    value = finding.get('value', '')[:60]
                    score = finding.get('relevance_score', 0)
                    output.append(f"      [{score}] {value}")
                if len(findings_list) > 3:
                    output.append(f"      ... y {len(findings_list) - 3} más")
            output.append("")
        
        output.append(f"{'='*60}\n")
        
        return '\n'.join(output)
