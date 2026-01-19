# services/worker/tasks/modules/web/selective_crawler.py

import time
import re
import urllib.parse
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
from ..base.base_searcher import BaseSearcher
from ..utils.result_filter import ResultFilter


class SelectiveCrawler(BaseSearcher):
    """Crawler selectivo: sólo sigue/enruta a URLs que probablemente contengan
    información relevante (perfiles sociales, páginas 'about', repositorios, etc.).

    Este módulo no intenta rastrear todo el sitio; en su lugar recibe una lista
    de candidatos (o toma los enlaces retornados por el search engine) y
    descarga y devuelve una colección limitada de páginas HTML para que los
    módulos extractores (MEI) las procesen.
    """

    def __init__(self):
        super().__init__()
        # simple policy
        self.social_domains = (
            'twitter.com', 'instagram.com', 'facebook.com', 'linkedin.com',
            'youtube.com', 'tiktok.com', 'github.com', 'about.me', 'medium.com'
        )
        # path keywords that often indicate personal/profile pages
        self.profile_path_keywords = ('/about', '/about-me', '/bio', '/profile', '/@', '/users/', '/u/', '/people/', '/author', '/contact')

    def get_supported_types(self) -> List[str]:
        return ["URL", "general"]

    def get_priority(self) -> int:
        # run early but after web spider
        return 2

    def search(self, query: str, search_type: str, options: Dict = None) -> Dict[str, Any]:
        options = options or {}
        candidates = options.get('candidates') or []
        max_pages = int(options.get('max_pages', 20))
        delay = float(options.get('pause', 0.6))

        # Accept either list of url strings or list of finding dicts
        urls = []
        for c in candidates:
            if not c:
                continue
            if isinstance(c, dict):
                v = c.get('value') or c.get('url')
            else:
                v = str(c)
            if not v:
                continue
            urls.append(v)

        # Heurística avanzada: score por heurísticas simples (dominio social, path, hostname)
        scored = []
        seen = set()
        # Break query into tokens to match against host/path/title
        name_tokens = []
        try:
            # simple split, preserve likely name tokens (e.g., 'Brad Pitt' -> ['brad','pitt'])
            name_tokens = [t.lower() for t in re.split(r'\s+', query) if t.strip()]
        except Exception:
            name_tokens = []

        for u in urls:
            low = u.lower()
            if low in seen:
                continue
            seen.add(low)

            score = 0
            # social domain boost
            if any(d in low for d in self.social_domains):
                score += 50

            # path keywords boost
            path = urllib.parse.urlparse(low).path
            for kw in self.profile_path_keywords:
                if kw in path:
                    score += 30
                    break

            # hostname contains any name token
            hostname = urllib.parse.urlparse(low).netloc
            for tok in name_tokens:
                if tok and tok in hostname:
                    score += 20
                    break

            # if URL contains username-like pattern (@ or /username)
            if re.search(r'/(?:@?)[A-Za-z0-9_.-]{3,}', path):
                score += 10

            scored.append((score, u))

        # Order candidates by score desc, then by original order for ties
        scored.sort(key=lambda x: x[0], reverse=True)
        final_list = [u for s, u in scored][:max_pages]

        raw_pages: Dict[str, str] = {}
        findings: List[Dict[str, Any]] = []

        for idx, url in enumerate(final_list):
            try:
                # brief delay to avoid hammering
                time.sleep(delay)
                resp = self._make_request(url)
                html = resp.text
                raw_pages[resp.url] = html

                # optional lightweight metadata extraction
                title = None
                try:
                    soup = BeautifulSoup(html, 'html.parser')
                    t = soup.find('title')
                    if t:
                        title = t.get_text().strip()
                except Exception:
                    title = None

                # Recompute a lightweight confidence based on title/path/name matches
                conf = 0.6
                low_url = resp.url.lower()
                low_title = (title or '').lower()
                # boost if social domain
                if any(d in low_url for d in self.social_domains):
                    conf += 0.25
                # boost if title or url contains name tokens
                for tok in name_tokens:
                    if tok and (tok in low_url or tok in low_title):
                        conf += 0.15
                        break
                # boost if path contains profile keywords
                for kw in self.profile_path_keywords:
                    if kw in urllib.parse.urlparse(low_url).path:
                        conf += 0.2
                        break

                findings.append({
                    'type': 'raw_page',
                    'value': resp.url,
                    'module': 'selective_crawler',
                    'title': title,
                    'rank': idx + 1,
                    'confidence': round(min(conf, 0.99), 2)
                })

            except Exception as e:
                self.logger.debug(f"SelectiveCrawler failed fetching {url}: {e}")
                continue

        return {
            'module': 'selective_crawler',
            'query': query,
            'search_type': search_type,
            'findings': ResultFilter.deduplicate_findings(findings),
            'raw_pages': raw_pages,
            'summary': {
                'candidates_received': len(urls),
                'pages_fetched': len(raw_pages)
            }
        }
