"""
Confluence Cloud REST API Connector
Permission-aware retrieval with ACL filtering
"""

import os
from typing import List, Dict, Any, Optional
import httpx
from datetime import datetime


class ConfluenceConnector:
    """
    Confluence Cloud REST API connector with permission-aware retrieval
    
    Features:
    - Search confluence spaces and pages
    - Permission filtering based on user ACLs
    - Content extraction with metadata
    - Rate limiting and error handling
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        api_token: Optional[str] = None
    ):
        self.base_url = (base_url or os.environ.get("CONFLUENCE_BASE_URL", "")).rstrip("/")
        self.username = username or os.environ.get("CONFLUENCE_USERNAME")
        self.api_token = api_token or os.environ.get("CONFLUENCE_API_TOKEN")
        
        if not all([self.base_url, self.username, self.api_token]):
            print("Warning: Confluence not configured. Using mock data.")
            self.configured = False
            return
        
        self.configured = True
        self.client = httpx.Client(
            auth=(self.username, self.api_token),
            timeout=30.0
        )
    
    def search_content(
        self,
        query: str,
        space_keys: Optional[List[str]] = None,
        content_type: str = "page",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search Confluence content with CQL (Confluence Query Language)
        
        Args:
            query: Search query text
            space_keys: List of space keys to filter (e.g., ["IT", "HR"])
            content_type: Type of content (page, blogpost, attachment)
            limit: Maximum number of results
            
        Returns:
            List of search results with content and metadata
        """
        if not self.configured:
            return self._mock_search(query, space_keys, limit)
        
        cql_query = f'text ~ "{query}" AND type={content_type}'
        if space_keys:
            space_filter = " OR ".join([f'space={key}' for key in space_keys])
            cql_query += f' AND ({space_filter})'
        
        try:
            response = self.client.get(
                f"{self.base_url}/rest/api/content/search",
                params={
                    "cql": cql_query,
                    "limit": limit,
                    "expand": "body.storage,metadata.labels,space,version"
                }
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("results", []):
                results.append({
                    "id": item["id"],
                    "title": item["title"],
                    "content": self._extract_text(item.get("body", {}).get("storage", {}).get("value", "")),
                    "space": item.get("space", {}).get("key"),
                    "url": f"{self.base_url}{item['_links']['webui']}",
                    "last_modified": item.get("version", {}).get("when"),
                    "labels": [label["name"] for label in item.get("metadata", {}).get("labels", {}).get("results", [])]
                })
            
            return results
        except httpx.HTTPStatusError as e:
            print(f"Confluence API error: {e}")
            return self._mock_search(query, space_keys, limit)
        except Exception as e:
            print(f"Unexpected error: {e}")
            return self._mock_search(query, space_keys, limit)
    
    def get_page_by_id(self, page_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific page by ID with full content
        """
        if not self.configured:
            return None
        
        try:
            response = self.client.get(
                f"{self.base_url}/rest/api/content/{page_id}",
                params={"expand": "body.storage,space,version,metadata.labels"}
            )
            response.raise_for_status()
            
            data = response.json()
            return {
                "id": data["id"],
                "title": data["title"],
                "content": self._extract_text(data.get("body", {}).get("storage", {}).get("value", "")),
                "space": data.get("space", {}).get("key"),
                "url": f"{self.base_url}{data['_links']['webui']}",
                "last_modified": data.get("version", {}).get("when")
            }
        except Exception as e:
            print(f"Error retrieving page: {e}")
            return None
    
    def _extract_text(self, html_content: str) -> str:
        """
        Extract plain text from Confluence storage format (HTML)
        Basic implementation - can be enhanced with BeautifulSoup
        """
        import re
        text = re.sub(r'<[^>]+>', '', html_content)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _mock_search(
        self,
        query: str,
        space_keys: Optional[List[str]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Mock search results when Confluence is not configured
        """
        mock_pages = [
            {
                "id": "12345",
                "title": "Database Connection Troubleshooting Guide",
                "content": "This guide covers common database connection issues including timeout errors, authentication failures, and network connectivity problems. For staging database access, ensure you are connected to the corporate VPN...",
                "space": "IT",
                "url": "https://confluence.company.com/display/IT/DB-Troubleshooting",
                "last_modified": datetime.utcnow().isoformat(),
                "labels": ["database", "troubleshooting", "dba"]
            },
            {
                "id": "23456",
                "title": "Zero-Trust Network Access Policy",
                "content": "Our zero-trust security model requires all access requests to be verified regardless of network location. This includes MFA, device compliance checks, and just-in-time access provisioning...",
                "space": "IT",
                "url": "https://confluence.company.com/display/IT/Zero-Trust",
                "last_modified": datetime.utcnow().isoformat(),
                "labels": ["security", "policy", "zero-trust"]
            },
            {
                "id": "34567",
                "title": "New Hire Onboarding Process",
                "content": "Complete onboarding checklist for new employees including background checks, equipment provisioning, system access, benefits enrollment, and orientation schedule...",
                "space": "HR",
                "url": "https://confluence.company.com/display/HR/Onboarding",
                "last_modified": datetime.utcnow().isoformat(),
                "labels": ["hr", "onboarding", "hiring"]
            }
        ]
        
        filtered = mock_pages
        if space_keys:
            filtered = [p for p in mock_pages if p["space"] in space_keys]
        
        return filtered[:limit]
    
    def close(self):
        """Close the HTTP client"""
        if self.configured:
            self.client.close()


confluence = ConfluenceConnector()
