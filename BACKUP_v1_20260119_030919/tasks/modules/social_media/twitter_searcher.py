# services/worker/tasks/modules/social_media/twitter_searcher.py

import requests
import json
import time
from typing import Dict, List, Any, Optional
from ..base.base_searcher import BaseSearcher
from ..utils.result_filter import ResultFilter
from datetime import datetime
import re
import urllib.parse
from bs4 import BeautifulSoup

class TwitterSearcher(BaseSearcher):
    """Twitter Searcher Mejorado - Búsquedas REALES"""
    
    def __init__(self):
        super().__init__()
        # Headers más realistas para evitar bloqueos
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        })
        
        # Rotar User-Agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        self.session.headers['User-Agent'] = user_agents[0]
    
    def search(self, query: str, search_type: str, options: Dict = None) -> Dict[str, Any]:
        """Búsqueda REAL y MEJORADA en Twitter"""
        try:
            self.logger.info(f"Buscando en Twitter: {query}")
            
            # Pequeña pausa para evitar rate limiting
            time.sleep(2)
            
            findings = []
            
            # Estrategias MEJORADAS según el tipo de búsqueda
            if search_type == "name":
                findings = self._search_by_name_improved(query)
            elif search_type == "email":
                findings = self._search_by_email_improved(query)
            elif search_type == "username":
                findings = self._search_by_username_improved(query)
            else:
                findings = self._search_general_improved(query)
            
            # Filtrar resultados irrelevantes
            filtered_findings = self._filter_relevant_findings(findings, query)
            
            return {
                "platform": "twitter",
                "query": query,
                "search_type": search_type,
                "findings": filtered_findings,
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "search_method": "web_scraping_improved",
                    "results_count": len(filtered_findings),
                    "original_results": len(findings),
                    "filtered_results": len(findings) - len(filtered_findings)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error en Twitter search: {e}")
            return {
                "error": str(e),
                "findings": [],
                "platform": "twitter"
            }
    
    def get_supported_types(self) -> List[str]:
        return ["name", "email", "username", "general"]
    
    def get_priority(self) -> int:
        return 3
    
    def _search_by_name_improved(self, name: str) -> List[Dict]:
        """Buscar perfiles REALES por nombre - MEJORADO"""
        findings = []
        
        try:
            # URL de búsqueda MÁS ESPECÍFICA
            search_url = f"https://twitter.com/search?q={urllib.parse.quote(name)}&f=user"
            
            self.logger.info(f"URL de búsqueda: {search_url}")
            
            response = self._make_request(search_url)
            
            # Extraer perfiles MEJORADO
            profiles = self._extract_profiles_from_html_improved(response.text, name)
            
            self.logger.info(f"Perfiles encontrados: {len(profiles)}")
            
            for profile in profiles:
                # CALCULAR CONFIANZA basada en relevancia
                relevance_score = self._calculate_relevance(profile, name)
                confidence = 0.3 + (relevance_score * 0.6)  # 0.3-0.9 basado en relevancia
                
                if relevance_score > 0.1:  # Solo incluir perfiles relevantes
                    findings.append({
                        "type": "social_profile",
                        "value": f"twitter.com/{profile['username']}",
                        "source": "twitter_search",
                        "confidence": round(confidence, 2),
                        "context": f"Perfil: {profile.get('display_name', profile['username'])}",
                        "metadata": {
                            "platform": "twitter",
                            "username": profile['username'],
                            "display_name": profile.get('display_name', ''),
                            "followers": profile.get('followers', 'N/A'),
                            "profile_url": f"https://twitter.com/{profile['username']}",
                            "relevance_score": round(relevance_score, 2),
                            "verified": profile.get('verified', False)
                        }
                    })
                
        except Exception as e:
            self.logger.warning(f"Error en búsqueda por nombre: {e}")
        
        # Fallback: si no encontramos perfiles directamente en twitter.com,
        # probamos una búsqueda pública (DuckDuckGo HTML) con site:twitter.com
        if not findings:
            try:
                self.logger.info("No se encontraron perfiles vía twitter.com, probando búsqueda alternativa (DuckDuckGo site:twitter.com)")
                ddg_profiles = self._search_site_twitter_via_duckduckgo(name)
                for profile in ddg_profiles:
                    relevance_score = self._calculate_relevance(profile, name)
                    confidence = 0.25 + (relevance_score * 0.65)
                    if relevance_score > 0.05:
                        findings.append({
                            "type": "social_profile",
                            "value": f"twitter.com/{profile['username']}",
                            "source": "twitter_search_fallback_ddg",
                            "confidence": round(confidence, 2),
                            "context": f"Perfil (fallback): {profile.get('display_name', profile['username'])}",
                            "metadata": {
                                "platform": "twitter",
                                "username": profile['username'],
                                "display_name": profile.get('display_name', profile['username']),
                                "followers": profile.get('followers', 'N/A'),
                                "profile_url": f"https://twitter.com/{profile['username']}",
                                "relevance_score": round(relevance_score, 2),
                                "verified": profile.get('verified', False)
                            }
                        })
            except Exception as e:
                self.logger.debug(f"Fallback DDG falló: {e}")

        # Cross-check authoritative pages (Wikipedia, IMDb) and add/boost candidates
        try:
            # If authoritative pages directly list twitter handles, add them as high-confidence
            wiki_users = self._check_wikipedia_for_twitter(name)
            imdb_users = self._check_imdb_for_twitter(name)
            authoritative = list(dict.fromkeys(wiki_users + imdb_users))

            for u in authoritative:
                # Avoid duplicates
                if not any((f.get('metadata', {}).get('username') or f.get('value','').split('/')[-1]).lower() == u.lower() for f in findings):
                    findings.append({
                        "type": "social_profile",
                        "value": f"twitter.com/{u}",
                        "source": "authoritative_check",
                        "confidence": 0.95,
                        "context": f"Found on authoritative pages (Wikipedia/IMDb): {u}",
                        "metadata": {
                            "platform": "twitter",
                            "username": u,
                            "display_name": u,
                            "followers": "N/A",
                            "profile_url": f"https://twitter.com/{u}",
                            "verified": False
                        }
                    })

            # Boost any candidates that match authoritative results
            findings = self._cross_check_candidates_against_authorities(name, findings)
        except Exception as e:
            self.logger.debug(f"Error during authoritative cross-check: {e}")

        return findings
    
    def _search_by_username_improved(self, username: str) -> List[Dict]:
        """Buscar perfil específico por username - MEJORADO"""
        findings = []
        
        try:
            # URL directa al perfil
            profile_url = f"https://twitter.com/{username}"
            
            self.logger.info(f"Verificando perfil: {profile_url}")
            
            response = self._make_request(profile_url)
            
            if response.status_code == 200:
                profile_data = self._extract_profile_details_improved(response.text, username)
                
                if profile_data and profile_data.get('exists', True):
                    findings.append({
                        "type": "social_profile",
                        "value": f"twitter.com/{username}",
                        "source": "twitter_direct",
                        "confidence": 0.9,
                        "context": f"Perfil de Twitter verificado",
                        "metadata": {
                            "platform": "twitter",
                            "username": username,
                            "display_name": profile_data.get('display_name', username),
                            "bio": profile_data.get('bio', ''),
                            "location": profile_data.get('location', ''),
                            "website": profile_data.get('website', ''),
                            "join_date": profile_data.get('join_date', ''),
                            "profile_url": profile_url,
                            "verified": profile_data.get('verified', False)
                        }
                    })
            else:
                self.logger.info(f"Perfil no encontrado: {username}")
                    
        except Exception as e:
            self.logger.warning(f"Error en búsqueda por username: {e}")
        
        return findings
    
    def _search_by_email_improved(self, email: str) -> List[Dict]:
        """Buscar posibles perfiles por email - MEJORADO"""
        findings = []
        
        try:
            # Extraer username del email para búsqueda
            username_from_email = email.split('@')[0]
            
            self.logger.info(f"Buscando por correo electrónico: {email} -> usuario: {username_from_email}")
            
            # Buscar por el username extraído del email
            email_findings = self._search_by_username_improved(username_from_email)
            findings.extend(email_findings)
            
            # Buscar también por el nombre completo del email (solo si tiene puntos)
            if '.' in username_from_email:
                name_from_email = username_from_email.replace('.', ' ').title()
                if ' ' in name_from_email:
                    name_findings = self._search_by_name_improved(name_from_email)
                    findings.extend(name_findings)
                
        except Exception as e:
            self.logger.warning(f"Error en búsqueda por email: {e}")
        
        return findings
    
    def _search_general_improved(self, query: str) -> List[Dict]:
        """Búsqueda general en Twitter - MEJORADO"""
        return self._search_by_name_improved(query)

    def _search_site_twitter_via_duckduckgo(self, query: str) -> List[Dict]:
        """Fallback: buscar en DuckDuckGo HTML usando site:twitter.com y extraer perfiles"""
        profiles = []
        try:
            # DuckDuckGo HTML endpoint (más consistente para scraping)
            q = f"site:twitter.com {query}"
            ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
            self.logger.debug(f"   URL de fallback DDG: {ddg_url}")

            resp = self._make_request(ddg_url)
            soup = BeautifulSoup(resp.text, 'html.parser')

            # Extraer enlaces de resultados y buscar twitter.com/username
            for a in soup.find_all('a', href=True):
                href = a['href']
                # DuckDuckGo may wrap urls in /l/?kh=-1&uddg=<encoded_url>
                if 'uddg=' in href:
                    try:
                        decoded = urllib.parse.unquote(href.split('uddg=')[-1])
                        href = decoded
                    except Exception:
                        pass

                m = re.search(r'twitter\.com/([A-Za-z0-9_]{1,15})(?:$|[/?#])', href)
                if m:
                    username = m.group(1)
                    if username.lower() not in ['home','explore','messages','i','search']:
                        display = a.get_text().strip() or username
                        profiles.append({
                            'username': username,
                            'display_name': display,
                            'followers': 'N/A',
                            'verified': False
                        })

            # Deduplicate
            uniq = []
            seen = set()
            for p in profiles:
                if p['username'] not in seen:
                    seen.add(p['username'])
                    uniq.append(p)

            return uniq

        except Exception as e:
            self.logger.debug(f"Error en DDG fallback: {e}")
            return profiles
    
    def _extract_profiles_from_html_improved(self, html: str, original_query: str) -> List[Dict]:
        """Extraer información REAL de perfiles del HTML - MEJORADO"""
        profiles = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # MÚLTIPLES ESTRATEGIAS para encontrar perfiles
            strategies = [
                self._extract_from_user_cells,
                self._extract_from_mentions,
                self._extract_from_twitter_links
            ]
            
            for strategy in strategies:
                try:
                    strategy_profiles = strategy(soup, original_query)
                    profiles.extend(strategy_profiles)
                except Exception as e:
                    self.logger.debug(f"Estrategia {strategy.__name__} falló: {e}")
            
            # Eliminar duplicados
            unique_profiles = []
            seen_usernames = set()
            for profile in profiles:
                if profile['username'] not in seen_usernames:
                    seen_usernames.add(profile['username'])
                    unique_profiles.append(profile)
            
            self.logger.info(f"Perfiles únicos encontrados: {len(unique_profiles)}")
            
            return unique_profiles
                    
        except Exception as e:
            self.logger.warning(f"Error extrayendo perfiles mejorado: {e}")
        
        return profiles
    
    def _extract_from_user_cells(self, soup: BeautifulSoup, original_query: str) -> List[Dict]:
        """Extraer perfiles de celdas de usuario"""
        profiles = []
        
        # Múltiples selectores para diferentes layouts de Twitter
        selectors = [
            'div[data-testid="UserCell"]',
            'div[role="article"]',
            'div.css-1dbjc4n.r-1iusvr4.r-16y2uox',
            'div[data-testid="User-Name"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements[:15]:  # Limitar resultados
                try:
                    # Extraer username de enlaces
                    links = element.find_all('a', href=re.compile(r'^/[\w]+$'))
                    for link in links:
                        username = link.get('href', '').lstrip('/')
                        if username and len(username) > 1 and not username.startswith('#'):
                            
                            # Extraer display name
                            display_name_elem = element.find(['span', 'div'], 
                                                           string=re.compile(r'[A-Za-z]'))
                            display_name = display_name_elem.get_text().strip() if display_name_elem else username
                            
                            # Verificar si es verified
                            verified = bool(element.find('svg[aria-label="Verified account"]') or 
                                          element.find('path[d*="M22.5 12.5c0-1.58"]'))
                            
                            profiles.append({
                                "username": username,
                                "display_name": display_name,
                                "followers": "N/A",
                                "verified": verified
                            })
                            break  # Solo un username por elemento
                            
                except Exception as e:
                    continue
                    
        return profiles
    
    def _extract_from_mentions(self, soup: BeautifulSoup, original_query: str) -> List[Dict]:
        """Extraer perfiles de menciones @username"""
        profiles = []
        text_content = soup.get_text()
        
        # Buscar menciones de Twitter
        username_pattern = r'@([A-Za-z0-9_]{1,15})'
        usernames = re.findall(username_pattern, text_content)
        
        for username in set(usernames[:10]):  # Limitar a 10 resultados
            if len(username) > 2:  # Filtrar usernames muy cortos
                profiles.append({
                    "username": username,
                    "display_name": username,
                    "followers": "N/A",
                    "verified": False
                })
        
        return profiles
    
    def _extract_from_twitter_links(self, soup: BeautifulSoup, original_query: str) -> List[Dict]:
        """Extraer perfiles de enlaces de Twitter"""
        profiles = []
        
        # Buscar enlaces a perfiles de Twitter
        twitter_links = soup.find_all('a', href=re.compile(r'https?://(?:www\.)?twitter\.com/[\w]+'))
        
        for link in twitter_links[:10]:
            try:
                href = link.get('href', '')
                username_match = re.search(r'twitter\.com/([A-Za-z0-9_]{1,15})', href)
                if username_match:
                    username = username_match.group(1)
                    if username.lower() not in ['home', 'explore', 'notifications', 'messages']:
                        profiles.append({
                            "username": username,
                            "display_name": link.get_text().strip() or username,
                            "followers": "N/A", 
                            "verified": False
                        })
            except Exception:
                continue
                
        return profiles
    
    def _extract_profile_details_improved(self, html: str, username: str) -> Optional[Dict]:
        """Extraer detalles MEJORADOS de un perfil"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Verificar si el perfil existe (no es página de error)
            error_indicators = ['Esta cuenta no existe', 'This account doesn\'t exist', 'Cuenta suspendida']
            page_text = soup.get_text()
            if any(indicator in page_text for indicator in error_indicators):
                return {"exists": False}
            
            profile_data = {
                "username": username,
                "display_name": username,
                "bio": "",
                "location": "",
                "website": "",
                "join_date": "",
                "verified": False,
                "exists": True
            }
            
            # Extraer display name
            display_name_selectors = [
                'div[data-testid="UserName"] span',
                'h1[role="heading"]',
                'div.css-1dbjc4n.r-1awozwy.r-18u37iz.r-1wbh5a2'
            ]
            
            for selector in display_name_selectors:
                elem = soup.select_one(selector)
                if elem and elem.get_text().strip():
                    profile_data["display_name"] = elem.get_text().strip()
                    break
            
            # Extraer bio
            bio_selectors = [
                'div[data-testid="UserDescription"]',
                'div.css-1dbjc4n.r-1adg3ll.r-6gpygo',
                'div[data-testid="UserBio"]'
            ]
            
            for selector in bio_selectors:
                elem = soup.select_one(selector)
                if elem and elem.get_text().strip():
                    profile_data["bio"] = elem.get_text().strip()
                    break
            
            # Verificar si es verified
            verified_indicators = [
                'svg[aria-label="Verified account"]',
                'path[d*="M22.5 12.5c0-1.58"]',
                'div[aria-label="Verified account"]'
            ]
            
            for indicator in verified_indicators:
                if soup.select_one(indicator):
                    profile_data["verified"] = True
                    break
            
            return profile_data
            
        except Exception as e:
            self.logger.warning(f"Error extrayendo detalles del perfil: {e}")
            return {"exists": True}  # Asumir que existe si hay error
    
    def _calculate_relevance(self, profile: Dict, original_name: str) -> float:
        """Calcular score de relevancia (0-1)"""
        score = 0.0
        name_parts = [part.lower() for part in original_name.split() if len(part) > 2]
        display_name = profile.get('display_name', '').lower()
        username = profile.get('username', '').lower()
        
        if not name_parts:
            return 0.1  # Mínima relevancia para nombres muy cortos
        
        # Coincidencia exacta del nombre completo
        if original_name.lower() in display_name:
            score += 0.6
        
        # Coincidencia de todas las partes del nombre
        all_parts_match = all(any(part in display_name for part in name_parts))
        if all_parts_match:
            score += 0.3
        
        # Coincidencia parcial de partes del nombre
        for part in name_parts:
            if part in display_name:
                score += 0.15
            if part in username:
                score += 0.1
        
        # Bonus por cuenta verificada
        if profile.get('verified', False):
            score += 0.2
        
        return min(score, 1.0)
    
    def _filter_relevant_findings(self, findings: List[Dict], original_query: str) -> List[Dict]:
        """Filtrar descubrimientos irrelevantes usando ResultFilter"""
        # Primero aplicar filtro general
        filtered = ResultFilter.clean_findings(findings, original_query)
        
        # Luego aplicar lógica específica de Twitter
        relevant_findings = []
        name_parts = [part.lower() for part in original_query.split() if len(part) > 2]
        
        for finding in filtered:
            metadata = finding.get('metadata', {})
            display_name = metadata.get('display_name', '').lower()
            username = metadata.get('username', '').lower()
            
            # Si no hay partes del nombre para comparar, incluir todos
            if not name_parts:
                relevant_findings.append(finding)
                continue
            
            # Verificar relevancia
            is_relevant = any(
                any(part in text for part in name_parts)
                for text in [display_name, username]
            )
            
            # Incluir también cuentas verificadas
            if is_relevant or metadata.get('verified', False) or finding.get('confidence', 0) > 0.6:
                relevant_findings.append(finding)
        
        return ResultFilter.deduplicate_findings(relevant_findings)

    # ---------------------
    # Cross-source verification helpers (free) - Wikipedia / IMDb
    # ---------------------
    def _check_wikipedia_for_twitter(self, name: str) -> List[str]:
        """Fetch the Wikipedia page for `name` (en) and return any twitter.com usernames linked on the page."""
        usernames = []
        try:
            # Build wiki title (replace spaces with underscores)
            title = name.strip().replace(' ', '_')
            url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}"
            self.logger.info(f"   Verificando Wikipedia para enlaces sociales: {url}")
            resp = self._make_request(url, allow_redirects=True)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Look for external links and infobox social links
            for a in soup.find_all('a', href=True):
                href = a['href']
                m = re.search(r'twitter\.com/([A-Za-z0-9_]{1,15})', href)
                if m:
                    u = m.group(1)
                    if u.lower() not in ['home','intent','share','search']:
                        usernames.append(u)
        except Exception as e:
            self.logger.debug(f"Error checking Wikipedia for {name}: {e}")
        return list(dict.fromkeys(usernames))

    def _check_imdb_for_twitter(self, name: str) -> List[str]:
        """Search IMDb for the person and try to find twitter links on their IMDb page. Returns usernames found."""
        usernames = []
        try:
            # Use IMDb search to find the candidate person page
            q = urllib.parse.quote(name)
            search_url = f"https://www.imdb.com/find?q={q}&s=nm"
            self.logger.info(f"   Buscando en IMDb: {search_url}")
            resp = self._make_request(search_url)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Find first name-result link
            first = soup.select_one('td.result_text a')
            if not first:
                return []
            person_href = first.get('href')
            person_url = urllib.parse.urljoin('https://www.imdb.com', person_href)
            # Visit person page
            self.logger.info(f"   Visitando página de persona en IMDb: {person_url}")
            p_resp = self._make_request(person_url)
            if p_resp.status_code != 200:
                return []
            p_soup = BeautifulSoup(p_resp.text, 'html.parser')
            # IMDb often places external links in a 'External Sites' or 'Official Sites' section or in the name's mini bio
            for a in p_soup.find_all('a', href=True):
                href = a['href']
                m = re.search(r'twitter\.com/([A-Za-z0-9_]{1,15})', href)
                if m:
                    u = m.group(1)
                    if u.lower() not in ['home','intent','share','search']:
                        usernames.append(u)
        except Exception as e:
            self.logger.debug(f"Error checking IMDb for {name}: {e}")
        return list(dict.fromkeys(usernames))

    def _cross_check_candidates_against_authorities(self, name: str, candidates: List[Dict]) -> List[Dict]:
        """Given candidate profile dicts (with 'username'), check authoritative pages (Wikipedia/IMDb) for twitter links.
        If a candidate is found on an authoritative page, boost its confidence and add context."""
        try:
            wiki_users = self._check_wikipedia_for_twitter(name)
            imdb_users = self._check_imdb_for_twitter(name)
            authoritative = set([u.lower() for u in (wiki_users + imdb_users)])

            if not authoritative:
                return candidates

            boosted = []
            for c in candidates:
                uname = c.get('metadata', {}).get('username') or c.get('value','').split('/')[-1]
                if uname.lower() in authoritative:
                    # Boost confidence and annotate
                    c['confidence'] = min(0.99, c.get('confidence', 0.5) + 0.25)
                    c['context'] = (c.get('context','') + ' | Found on authoritative pages (Wikipedia/IMDb)').strip(' |')
                    c['source'] = (c.get('source','search') + '_authoritative').strip('_')
                boosted.append(c)

            return boosted
        except Exception as e:
            self.logger.debug(f"Error during cross-check: {e}")
            return candidates