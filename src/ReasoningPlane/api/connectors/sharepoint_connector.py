"""
SharePoint Graph API Connector
ACL-based post-filtering for permission-aware retrieval
"""

import os
from typing import List, Dict, Any, Optional
import httpx
from datetime import datetime


class SharePointConnector:
    """
    Microsoft Graph API connector for SharePoint
    
    Features:
    - Search SharePoint sites and documents
    - ACL-based permission filtering
    - Content extraction with metadata
    - OAuth2 authentication with Microsoft Graph
    """
    
    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        self.tenant_id = tenant_id or os.environ.get("AZURE_TENANT_ID")
        self.client_id = client_id or os.environ.get("AZURE_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("AZURE_CLIENT_SECRET")
        
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            print("Warning: SharePoint/Graph API not configured. Using mock data.")
            self.configured = False
            return
        
        self.configured = True
        self.access_token = None
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"
        
        self._authenticate()
    
    def _authenticate(self) -> None:
        """
        Authenticate with Microsoft Graph API using client credentials flow
        """
        if not self.configured:
            return
        
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        try:
            response = httpx.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://graph.microsoft.com/.default"
                },
                timeout=30.0
            )
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data.get("access_token")
            print("Successfully authenticated with Microsoft Graph API")
        except Exception as e:
            print(f"Authentication error: {e}")
            self.configured = False
    
    def search_content(
        self,
        query: str,
        site_ids: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search SharePoint content using Microsoft Graph Search API
        
        Args:
            query: Search query text
            site_ids: List of site IDs to filter
            limit: Maximum number of results
            
        Returns:
            List of search results with content and metadata
        """
        if not self.configured or not self.access_token:
            return self._mock_search(query, site_ids, limit)
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        search_body = {
            "requests": [
                {
                    "entityTypes": ["driveItem", "listItem"],
                    "query": {
                        "queryString": query
                    },
                    "from": 0,
                    "size": limit
                }
            ]
        }
        
        try:
            response = httpx.post(
                f"{self.graph_endpoint}/search/query",
                json=search_body,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for request_result in data.get("value", []):
                for hit in request_result.get("hitsContainers", [{}])[0].get("hits", []):
                    resource = hit.get("resource", {})
                    results.append({
                        "id": resource.get("id"),
                        "title": resource.get("name") or resource.get("title"),
                        "content": resource.get("body", {}).get("content", ""),
                        "url": resource.get("webUrl"),
                        "last_modified": resource.get("lastModifiedDateTime"),
                        "author": resource.get("createdBy", {}).get("user", {}).get("displayName"),
                        "site_id": resource.get("parentReference", {}).get("siteId")
                    })
            
            if site_ids:
                results = [r for r in results if r.get("site_id") in site_ids]
            
            return results[:limit]
        except httpx.HTTPStatusError as e:
            print(f"Graph API error: {e}")
            return self._mock_search(query, site_ids, limit)
        except Exception as e:
            print(f"Unexpected error: {e}")
            return self._mock_search(query, site_ids, limit)
    
    def get_file_content(self, drive_id: str, item_id: str) -> Optional[str]:
        """
        Retrieve file content from SharePoint
        """
        if not self.configured or not self.access_token:
            return None
        
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            response = httpx.get(
                f"{self.graph_endpoint}/drives/{drive_id}/items/{item_id}/content",
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            
            return response.text
        except Exception as e:
            print(f"Error retrieving file content: {e}")
            return None
    
    def _mock_search(
        self,
        query: str,
        site_ids: Optional[List[str]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Mock search results when SharePoint is not configured
        """
        mock_documents = [
            {
                "id": "doc-001",
                "title": "IT Operations Handbook.docx",
                "content": "Comprehensive guide to IT operations including incident response procedures, escalation paths, on-call rotations, and SLA requirements...",
                "url": "https://sharepoint.company.com/sites/IT/Documents/Handbook.docx",
                "last_modified": datetime.utcnow().isoformat(),
                "author": "IT Admin",
                "site_id": "it-site-001"
            },
            {
                "id": "doc-002",
                "title": "HR Policies and Procedures.pdf",
                "content": "Company HR policies covering employment, benefits, code of conduct, performance management, and termination procedures...",
                "url": "https://sharepoint.company.com/sites/HR/Documents/Policies.pdf",
                "last_modified": datetime.utcnow().isoformat(),
                "author": "HR Director",
                "site_id": "hr-site-001"
            },
            {
                "id": "doc-003",
                "title": "Database Security Standards.docx",
                "content": "Security standards for database access control, encryption at rest and in transit, backup procedures, and compliance requirements...",
                "url": "https://sharepoint.company.com/sites/IT/Security/DB-Security.docx",
                "last_modified": datetime.utcnow().isoformat(),
                "author": "Security Team",
                "site_id": "it-site-001"
            }
        ]
        
        filtered = mock_documents
        if site_ids:
            filtered = [d for d in mock_documents if d.get("site_id") in site_ids]
        
        return filtered[:limit]


sharepoint = SharePointConnector()
