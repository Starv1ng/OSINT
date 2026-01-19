# services/worker/tasks/modules/search_engine/search_engine_searcher.py

import urllib.parse
import re
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from ..base.base_searcher import BaseSearcher
from ..utils.result_filter import ResultFilter

# Import TwitterSearcher to validate candidate usernames
from ..social_media.twitter_searcher import TwitterSearcher


class SearchEngineSearcher(BaseSearcher):
    """General Search Engine module.

    Tries Google first (best-effort) and falls back to DuckDuckGo HTML scraping.
    Returns generic findings (links) that other modules can consume.
    """

    def __init__(self):
        super().__init__()
        # Polite headers
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        # Simple UA rotation list - will pick one per search
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (compatible; OSINT-Bot/1.0; +https://example.com/bot)'
        ]
        self.session.headers.setdefault('User-Agent', self.user_agents[0])
        # Human-like settings
        self.humanize_default = True
        self.referers = [
            'https://www.google.com/', 'https://www.bing.com/', 'https://duckduckgo.com/',
            'https://www.wikipedia.org/', 'https://www.facebook.com/'
        ]

    def get_supported_types(self) -> List[str]:
        return ["general", "person", "company", "username", "email"]

    def get_priority(self) -> int:
        # Low number = higher priority; keep it moderate so other specialized modules can run
        return 5

    def search(self, query: str, search_type: str, options: Dict = None) -> Dict[str, Any]:
        options = options or {}
        engine = options.get('engine', 'auto')  # 'google', 'duckduckgo', or 'auto'
        # Allow caller to pass proxies or serpapi key via options
        proxies = options.get('proxies')
        serpapi_key = options.get('serpapi_key') or options.get('SERPAPI_KEY')

        # Apply proxies to session for this request if provided
        if proxies:
            try:
                self.session.proxies.update(proxies)
            except Exception:
                pass

        self.logger.info(f"Búsqueda en motor de búsqueda ({engine}): {query}")

        try:
            findings: List[Dict] = []

            # If user requests explicit engine, honor it; otherwise try Google then DDG
            last_raw_html = None
            if engine in ('google', 'auto'):
                try:
                    # rotate UA for each google attempt to reduce chance of challenge
                    self.session.headers['User-Agent'] = self.user_agents[hash(query) % len(self.user_agents)]
                    # If an API key for SerpAPI is provided, use it first (more reliable)
                    if serpapi_key:
                        findings, raw = self._search_serpapi(query, serpapi_key, humanize=options.get('humanize', self.humanize_default))
                    else:
                        findings, raw = self._search_google(query, humanize=options.get('humanize', self.humanize_default))
                    last_raw_html = raw
                    if findings:
                        return self._wrap_results(query, search_type, findings, 'google', raw_html=last_raw_html, validate_profiles=options.get('validate_profiles', False))
                except Exception as e:
                    self.logger.debug(f"Google search failed or blocked: {e}")

            # Try Bing HTML before DuckDuckGo - Bing often returns HTML results more scrape-friendly
            try:
                findings, raw = self._search_bing(query, humanize=options.get('humanize', self.humanize_default))
                last_raw_html = raw
                if findings:
                    return self._wrap_results(query, search_type, findings, 'bing', raw_html=last_raw_html, validate_profiles=options.get('validate_profiles', False))
            except Exception as e:
                self.logger.debug(f"Bing fallback failed: {e}")

            # Fallback: DuckDuckGo HTML
            try:
                findings, raw = self._search_duckduckgo(query, humanize=options.get('humanize', self.humanize_default))
                last_raw_html = raw
                return self._wrap_results(query, search_type, findings, 'duckduckgo', raw_html=last_raw_html, validate_profiles=options.get('validate_profiles', False))
            except Exception as e:
                self.logger.debug(f"DuckDuckGo fallback failed: {e}")

            return self._wrap_results(query, search_type, [], 'none', validate_profiles=options.get('validate_profiles', False))

        except Exception as e:
            self.logger.error(f"SearchEngine error: {e}")
            return {"error": str(e), "findings": []}

    def _wrap_results(self, query: str, search_type: str, findings: List[Dict], engine: str, raw_html: Optional[str] = None, validate_profiles: bool = False) -> Dict[str, Any]:
        # After collecting raw link findings, optionally extract twitter usernames
        # and validate them. By default this is disabled so the search engine
        # module only performs search and returns links/raw_html. Validation is
        # an optional, potentially expensive operation and should be requested
        # explicitly via options (validate_profiles=True).
        
        # APLICAR FILTROS para eliminar ruido
        findings = ResultFilter.clean_findings(findings, query)
        
        twitter_profiles = []
        if validate_profiles:
            try:
                twitter_profiles = self._extract_and_validate_twitter_profiles(findings)
            except Exception:
                twitter_profiles = []

        # Append validated twitter profiles to findings (higher priority)
        all_findings = list(twitter_profiles) + list(findings)
        
        # APLICAR FILTROS FINALES y deduplicación
        all_findings = ResultFilter.deduplicate_findings(all_findings)

        result = {
            "platform": "search_engine",
            "query": query,
            "search_type": search_type,
            "engine": engine,
            "findings": all_findings,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "results_count": len(all_findings)
            }
        }

        # Include raw HTML of the search result page for MEI modules to extract indicators
        if raw_html:
            result['raw_html'] = raw_html

        return result

    def _extract_and_validate_twitter_profiles(self, link_findings: List[Dict]) -> List[Dict]:
        """From a list of link findings, extract twitter.com usernames and validate
        by fetching profile pages. Returns normalized social_profile findings.
        """
        candidates = []
        for f in link_findings:
            url = f.get('value', '')
            if not url:
                continue
            m = re.search(r'twitter\.com/([A-Za-z0-9_]{1,15})(?:$|[/?#])', url)
            if m:
                uname = m.group(1)
                if uname.lower() not in ['home', 'explore', 'i', 'search', 'messages', 'notifications']:
                    candidates.append(uname)

        # Deduplicate
        uniq = []
        seen = set()
        for u in candidates:
            if u not in seen:
                seen.add(u)
                uniq.append(u)

        validated: List[Dict] = []
        if not uniq:
            return []

        # Use TwitterSearcher parsing helpers to validate and extract display names
        ts = TwitterSearcher()
        for uname in uniq[:30]:  # limit validation attempts
            try:
                profile_url = f'https://twitter.com/{uname}'
                resp = self._make_request(profile_url)
                if resp.status_code != 200:
                    continue
                details = ts._extract_profile_details_improved(resp.text, uname)
                if details and details.get('exists', True):
                    validated.append({
                        'type': 'social_profile',
                        'value': f'twitter.com/{uname}',
                        'source': 'search_engine_validated',
                        'confidence': 0.9 if details.get('verified', False) else 0.7,
                        'context': f'Validated Twitter profile for {uname}',
                        'metadata': {
                            'platform': 'twitter',
                            'username': uname,
                            'display_name': details.get('display_name', uname),
                            'verified': details.get('verified', False),
                            'profile_url': profile_url
                        }
                    })
            except Exception as e:
                self.logger.debug(f"Error validating twitter username {uname}: {e}")

        return validated

    def _humanized_request(self, url: str, params: Dict = None, humanize: bool = True, method: str = 'GET', **kwargs):
        """Perform a request with small human-like behaviors to reduce bot detection.

        - Random short sleep with jitter
        - Rotate User-Agent and set a plausible Referer
        - Occasionally perform a HEAD before GET
        """
        headers = kwargs.pop('headers', {}) or {}

        # Apply UA rotation
        ua = self.user_agents[hash(url + (params.get('q') if params and 'q' in params else '')) % len(self.user_agents)]
        headers.setdefault('User-Agent', ua)

        # Random referer
        headers.setdefault('Referer', random.choice(self.referers))
        headers.setdefault('Accept-Language', random.choice(['en-US,en;q=0.9', 'en-GB,en;q=0.9', 'es-ES,es;q=0.9']))
        # Additional realistic headers
        headers.setdefault('Upgrade-Insecure-Requests', '1')
        headers.setdefault('Sec-Fetch-Site', 'none')
        headers.setdefault('Sec-Fetch-Mode', 'navigate')
        headers.setdefault('Sec-Fetch-User', '?1')
        headers.setdefault('Sec-Fetch-Dest', 'document')
        # Client hints (simple)
        headers.setdefault('Sec-CH-UA', '"Chromium";v="120", "Not)A;Brand";v="99"')
        headers.setdefault('Sec-CH-UA-Mobile', '?0')

        # Human-like delay
        if humanize:
            delay = random.uniform(0.6, 1.6)
            # small chance of slightly longer pause
            if random.random() < 0.05:
                delay += random.uniform(1.0, 3.0)
            time.sleep(delay)

        # Occasionally do a simple GET to the site root to obtain cookies and mimic a human landing
        if humanize and random.random() < 0.35:
            try:
                base = urllib.parse.urlparse(url)
                root = f"{base.scheme}://{base.netloc}/"
                self.session.get(root, timeout=8, headers={'User-Agent': ua, 'Referer': random.choice(self.referers)})
            except Exception:
                pass

        # Occasionally do a HEAD to mimic browser preflight
        if humanize and random.random() < 0.18:
            try:
                self.session.request('HEAD', url, timeout=10, headers=headers)
            except Exception:
                pass

        # Use BaseSearcher request wrapper (will raise on bad status)
        response = self._make_request(url, method=method, params=params, headers=headers, **kwargs)
        return response

    def _search_google(self, query: str, humanize: bool = True) -> List[Dict]:
        """Attempt a best-effort Google search scraping.

        Note: Google often blocks scraping; this is best-effort and will fall back to DDG.
        """
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        self.logger.debug(f"   → Google URL: {url}")
        resp = self._humanized_request(url, params=None, humanize=humanize)
        if resp.status_code != 200:
            raise RuntimeError(f"Google returned status {resp.status_code}")

        # Detect obvious JS/challenge pages
        if '/httpservice/retry/enablejs' in resp.text or 'To continue, please enable JavaScript' in resp.text:
            raise RuntimeError('Google returned JS-challenge page')

        soup = BeautifulSoup(resp.text, 'html.parser')
        findings: List[Dict] = []

        anchors = []
        # prefer structured result containers
        for div in soup.select('div.g, div.yuRUbf, div.rc'):
            a = div.select_one('a[href]')
            if a:
                anchors.append(a)

        # fallback to any anchor
        if not anchors:
            anchors = soup.select('a[href]')

        seen = set()
        rank = 1
        for a in anchors:
            href = a.get('href')
            if not href:
                continue
            # sometimes google wraps urls like /url?q=<url>&sa=...
            m = re.search(r'/url\?q=([^&]+)', href)
            if m:
                href = urllib.parse.unquote(m.group(1))

            # normalize relative URLs
            if href.startswith('/'):
                try:
                    href = urllib.parse.urljoin('https://www.google.com', href)
                except Exception:
                    pass

            # filter out google internals
            if 'google.com' in href or href.startswith('/search'):
                continue

            if href in seen:
                continue
            seen.add(href)

            title = a.get_text().strip() or None
            findings.append({
                'type': 'link',
                'value': href,
                'source': 'google',
                'rank': rank,
                'title': title,
                'confidence': round(max(0.2, 1.0 - (rank * 0.05)), 2)
            })
            rank += 1
            if rank > 50:
                break
            if rank > 50:
                break

        # Return findings and raw HTML for downstream extraction
        return findings, resp.text

    def _search_duckduckgo(self, query: str, humanize: bool = True) -> List[Dict]:
        q = query
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
        self.logger.debug(f"   → DuckDuckGo URL: {url}")
        resp = self._humanized_request(url, params=None, humanize=humanize)
        if resp.status_code != 200:
            raise RuntimeError(f"DuckDuckGo returned status {resp.status_code}")

        soup = BeautifulSoup(resp.text, 'html.parser')
        findings: List[Dict] = []
        seen = set()
        rank = 1

        # DuckDuckGo result links are in a.results__a or <a class="result__a">
        for a in soup.select('a.result__a, a[href]'):
            href = a.get('href')
            if not href:
                continue
            # DDG may wrap urls in /l/?kh=-1&uddg=<encoded_url>
            if 'uddg=' in href:
                try:
                    href = urllib.parse.unquote(href.split('uddg=')[-1])
                except Exception:
                    pass

            # Normalize
            if href in seen:
                continue
            if 'duckduckgo.com' in href:
                continue

            seen.add(href)
            title = a.get_text().strip() or None
            findings.append({
                'type': 'link',
                'value': href,
                'source': 'duckduckgo',
                'rank': rank,
                'title': title,
                'confidence': round(max(0.2, 1.0 - (rank * 0.04)), 2)
            })
            rank += 1
            if rank > 50:
                break
        # Return findings and raw HTML for downstream extraction
        return findings, resp.text

    def _search_bing(self, query: str, humanize: bool = True) -> List[Dict]:
        """Search Bing HTML results (best-effort scraping)."""
        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        self.logger.debug(f"   → Bing URL: {url}")
        resp = self._humanized_request(url, params=None, humanize=humanize)
        if resp.status_code != 200:
            raise RuntimeError(f"Bing returned status {resp.status_code}")

        soup = BeautifulSoup(resp.text, 'html.parser')
        findings: List[Dict] = []
        seen = set()
        rank = 1

        # Bing results commonly live in <li class="b_algo"> with an <a>
        for li in soup.select('li.b_algo'):
            a = li.select_one('a[href]')
            if not a:
                continue
            href = a.get('href')
            if not href or 'bing.com' in href:
                continue
            if href in seen:
                continue
            seen.add(href)
            title = a.get_text().strip() or None
            findings.append({
                'type': 'link',
                'value': href,
                'source': 'bing',
                'rank': rank,
                'title': title,
                'confidence': round(max(0.2, 1.0 - (rank * 0.04)), 2)
            })
            rank += 1
            if rank > 50:
                break

        # Return findings and raw HTML for downstream extraction
        return findings, resp.text

    def _search_serpapi(self, query: str, api_key: str, humanize: bool = True) -> List[Dict]:
        """Use SerpAPI if an API key is provided (safer than scraping)."""
        try:
            params = {
                'q': query,
                'api_key': api_key,
                'engine': 'google'
            }
            url = 'https://serpapi.com/search.json'
            resp = self._humanized_request(url, params=params, humanize=True)
            if resp.status_code != 200:
                raise RuntimeError(f"SerpAPI returned {resp.status_code}")
            data = resp.json()
            findings: List[Dict] = []
            rank = 1
            for item in data.get('organic_results', [])[:50]:
                href = item.get('link') or item.get('url')
                if not href:
                    continue
                findings.append({
                    'type': 'link',
                    'value': href,
                    'source': 'serpapi',
                    'rank': rank,
                    'title': item.get('title'),
                    'confidence': round(max(0.3, 1.0 - (rank * 0.03)), 2)
                })
                rank += 1
            # Return findings and the raw response body so callers can provide
            # the raw HTML/JSON to downstream MEI extractors if desired.
            return findings, resp.text
        except Exception as e:
            self.logger.debug(f"SerpAPI failed: {e}")
            return [], None

