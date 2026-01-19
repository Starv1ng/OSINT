# services/worker/tasks/modules/development/github_searcher.py

import requests
import re
import time
from typing import Dict, List, Any, Optional
from ..base.base_searcher import BaseSearcher
from datetime import datetime
import urllib.parse

class GitHubSearcher(BaseSearcher):
    """GitHub Searcher - Búsquedas de usuarios, repositorios y código"""
    
    def __init__(self):
        super().__init__()
        self.api_base = "https://api.github.com"
        self.web_base = "https://github.com"
        
        # GitHub permite 60 requests/hora sin token
        # Con token permite 5000 requests/hora
        self.token = None  # Se puede pasar vía options
        
        if self.token:
            self.session.headers['Authorization'] = f'token {self.token}'
    
    def get_supported_types(self) -> List[str]:
        return ["username", "email", "person", "company"]
    
    def get_priority(self) -> int:
        return 7
    
    def search(self, query: str, search_type: str, options: Dict = None) -> Dict[str, Any]:
        """
        Búsqueda en GitHub (público)
        """
        try:
            options = options or {}
            self.token = options.get('github_token') or options.get('GITHUB_TOKEN')
            
            if self.token:
                self.session.headers['Authorization'] = f'token {self.token}'
            
            self.logger.info(f"Buscando en GitHub: {query} (tipo: {search_type})")
            
            findings = []
            
            if search_type == "username":
                findings = self._search_user(query)
            elif search_type == "email":
                findings = self._search_by_email(query)
            elif search_type == "person":
                findings = self._search_user(query)
            elif search_type == "company":
                findings = self._search_organization(query)
            else:
                findings = self._search_user(query)
            
            return {
                "module": "github_searcher",
                "query": query,
                "search_type": search_type,
                "findings": findings,
                "timestamp": datetime.now().isoformat(),
                "success": len(findings) > 0
            }
        except Exception as e:
            self.logger.error(f"Error en búsqueda GitHub: {e}")
            return {
                "module": "github_searcher",
                "query": query,
                "search_type": search_type,
                "findings": [],
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "success": False
            }
    
    def _search_user(self, username: str) -> List[Dict[str, Any]]:
        """Buscar usuario por username"""
        findings = []
        try:
            # Buscar en API de GitHub
            url = f"{self.api_base}/search/users?q={urllib.parse.quote(username)}&per_page=5"
            
            time.sleep(1)  # Rate limiting
            response = self._make_request(url)
            
            if response.status_code == 200:
                data = response.json()
                for user in data.get('items', []):
                    finding = {
                        "type": "github_user",
                        "username": user['login'],
                        "url": user['html_url'],
                        "avatar": user.get('avatar_url'),
                        "public_repos": user.get('public_repos', 0),
                        "followers": user.get('followers', 0),
                        "bio": user.get('bio'),
                        "company": user.get('company'),
                        "location": user.get('location'),
                        "email": user.get('email'),
                        "blog": user.get('blog'),
                        "source": "github",
                        "confidence": 0.9
                    }
                    findings.append(finding)
                    
                    # Si es una coincidencia exacta, obtener más detalles
                    if user['login'].lower() == username.lower():
                        self._get_user_details(user['login'], finding)
        except Exception as e:
            self.logger.debug(f"Error buscando usuario en GitHub: {e}")
        
        return findings
    
    def _get_user_details(self, username: str, finding: Dict) -> None:
        """Obtener detalles adicionales del usuario"""
        try:
            url = f"{self.api_base}/users/{username}"
            response = self._make_request(url)
            
            if response.status_code == 200:
                data = response.json()
                finding.update({
                    "created_at": data.get('created_at'),
                    "updated_at": data.get('updated_at'),
                    "public_gists": data.get('public_gists', 0),
                    "twitter_username": data.get('twitter_username'),
                    "hireable": data.get('hireable'),
                    "gravatar_id": data.get('gravatar_id'),
                })
                
                # Obtener repos principales
                repos_url = f"{self.api_base}/users/{username}/repos?sort=stars&per_page=3"
                repos_response = self._make_request(repos_url)
                if repos_response.status_code == 200:
                    repos = repos_response.json()
                    finding['top_repos'] = [
                        {
                            'name': r['name'],
                            'url': r['html_url'],
                            'description': r.get('description'),
                            'stars': r.get('stargazers_count', 0)
                        }
                        for r in repos[:3]
                    ]
        except Exception as e:
            self.logger.debug(f"Error obteniendo detalles: {e}")
    
    def _search_by_email(self, email: str) -> List[Dict[str, Any]]:
        """Buscar por email (búsqueda de código)"""
        findings = []
        try:
            # GitHub permite buscar commits/código por email
            url = f"{self.api_base}/search/commits?q=author:{urllib.parse.quote(email)}&per_page=5"
            
            time.sleep(1)
            response = self._make_request(url)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('total_count', 0) > 0:
                    finding = {
                        "type": "github_email",
                        "email": email,
                        "commits_count": data.get('total_count', 0),
                        "source": "github",
                        "confidence": 0.85,
                        "note": "Email encontrado en commits de código"
                    }
                    findings.append(finding)
        except Exception as e:
            self.logger.debug(f"Error buscando por email: {e}")
        
        return findings
    
    def _search_organization(self, org_name: str) -> List[Dict[str, Any]]:
        """Buscar organización"""
        findings = []
        try:
            url = f"{self.api_base}/search/users?q={urllib.parse.quote(org_name)}+type:org&per_page=5"
            
            time.sleep(1)
            response = self._make_request(url)
            
            if response.status_code == 200:
                data = response.json()
                for org in data.get('items', []):
                    finding = {
                        "type": "github_organization",
                        "name": org['login'],
                        "url": org['html_url'],
                        "avatar": org.get('avatar_url'),
                        "public_repos": org.get('public_repos', 0),
                        "followers": org.get('followers', 0),
                        "source": "github",
                        "confidence": 0.85
                    }
                    findings.append(finding)
        except Exception as e:
            self.logger.debug(f"Error buscando organización: {e}")
        
        return findings
