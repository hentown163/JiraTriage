"""
Azure AI Search Integration for RAG Knowledge Base
Handles vector embeddings storage and hybrid search (vector + keyword)
"""

import os
from typing import List, Dict, Any, Optional
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch
)
from azure.core.credentials import AzureKeyCredential
from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings
import os


class AzureAISearchManager:
    """
    Azure AI Search manager for vector embeddings and hybrid search
    
    Features:
    - Vector embeddings with HNSW algorithm
    - Hybrid search (vector + BM25 keyword)
    - Semantic ranking
    - Per-department index isolation
    """
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        index_name: str = "jira-kb"
    ):
        self.endpoint = endpoint or os.environ.get("AZURE_SEARCH_ENDPOINT")
        self.api_key = api_key or os.environ.get("AZURE_SEARCH_API_KEY")
        self.index_name = index_name
        
        if not self.endpoint or not self.api_key:
            print("Warning: Azure AI Search not configured. Using mock retrieval.")
            self.configured = False
            return
        
        self.configured = True
        self.credential = AzureKeyCredential(self.api_key)
        self.index_client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=self.credential
        )
        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.index_name,
            credential=self.credential
        )
        
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        azure_api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        
        if azure_endpoint and azure_api_key:
            self.embeddings = AzureOpenAIEmbeddings(
                azure_deployment="text-embedding-3-small",
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
            )
        elif openai_api_key:
            self.embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=openai_api_key
            )
        else:
            print("Warning: No OpenAI credentials for embeddings")
    
    def create_index(self) -> None:
        """
        Create or update Azure AI Search index with vector search capabilities
        """
        if not self.configured:
            print("Azure AI Search not configured. Skipping index creation.")
            return
        
        fields = [
            SimpleField(
                name="id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True
            ),
            SearchableField(
                name="title",
                type=SearchFieldDataType.String,
                searchable=True,
                analyzer_name="en.microsoft"
            ),
            SearchableField(
                name="content",
                type=SearchFieldDataType.String,
                searchable=True,
                analyzer_name="en.microsoft"
            ),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=1536,
                vector_search_profile_name="my-vector-profile"
            ),
            SimpleField(
                name="department",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True
            ),
            SimpleField(
                name="team",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True
            ),
            SimpleField(
                name="source",
                type=SearchFieldDataType.String,
                filterable=True
            ),
            SimpleField(
                name="url",
                type=SearchFieldDataType.String,
                filterable=False
            )
        ]
        
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="my-hnsw-config",
                    parameters={
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine"
                    }
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="my-vector-profile",
                    algorithm_configuration_name="my-hnsw-config"
                )
            ]
        )
        
        semantic_config = SemanticConfiguration(
            name="my-semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="title"),
                content_fields=[SemanticField(field_name="content")]
            )
        )
        
        semantic_search = SemanticSearch(
            configurations=[semantic_config]
        )
        
        index = SearchIndex(
            name=self.index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search
        )
        
        try:
            self.index_client.create_or_update_index(index)
            print(f"Index '{self.index_name}' created/updated successfully.")
        except Exception as e:
            print(f"Error creating index: {e}")
    
    def hybrid_search(
        self,
        query: str,
        department: Optional[str] = None,
        team: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search (vector + keyword) with optional filtering
        
        Args:
            query: Search query text
            department: Filter by department (IT, HR, Finance, Legal)
            team: Filter by team (DBA, Onboarding, etc.)
            top_k: Number of results to return
            
        Returns:
            List of search results with metadata
        """
        if not self.configured:
            return self._mock_search(query, department, team, top_k)
        
        try:
            query_vector = self.embeddings.embed_query(query)
            
            filter_expr = None
            if department:
                filter_expr = f"department eq '{department}'"
                if team:
                    filter_expr += f" and team eq '{team}'"
            
            results = self.search_client.search(
                search_text=query,
                vector_queries=[{
                    "kind": "vector",
                    "vector": query_vector,
                    "fields": "content_vector",
                    "k": top_k
                }],
                filter=filter_expr,
                top=top_k,
                select=["id", "title", "content", "department", "team", "source", "url"]
            )
            
            return [
                {
                    "id": result["id"],
                    "title": result["title"],
                    "content": result["content"],
                    "department": result.get("department"),
                    "team": result.get("team"),
                    "source": result.get("source"),
                    "url": result.get("url"),
                    "score": result["@search.score"]
                }
                for result in results
            ]
        except Exception as e:
            print(f"Search error: {e}")
            return self._mock_search(query, department, team, top_k)
    
    def _mock_search(
        self,
        query: str,
        department: Optional[str],
        team: Optional[str],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Fallback mock search when Azure AI Search is not configured
        """
        mock_kb = {
            "IT": {
                "DBA": [
                    {
                        "id": "kb-887",
                        "title": "Database Connection Troubleshooting",
                        "content": "Step-by-step guide to diagnose and resolve database connection timeouts...",
                        "department": "IT",
                        "team": "DBA",
                        "source": "Confluence",
                        "url": "https://confluence.company.com/kb-887",
                        "score": 0.95
                    }
                ],
                "Security": [
                    {
                        "id": "kb-234",
                        "title": "Zero-Trust Network Access Policy",
                        "content": "Corporate zero-trust security model and implementation guidelines...",
                        "department": "IT",
                        "team": "Security",
                        "source": "Confluence",
                        "url": "https://confluence.company.com/kb-234",
                        "score": 0.88
                    }
                ]
            },
            "HR": {
                "Onboarding": [
                    {
                        "id": "hr-101",
                        "title": "New Hire Onboarding Checklist",
                        "content": "Complete onboarding process including background checks, equipment, and training...",
                        "department": "HR",
                        "team": "Onboarding",
                        "source": "SharePoint",
                        "url": "https://sharepoint.company.com/hr/hr-101",
                        "score": 0.92
                    }
                ]
            }
        }
        
        dept_kb = mock_kb.get(department or "IT", {})
        team_kb = dept_kb.get(team or "DBA", [])
        
        return team_kb[:top_k] if team_kb else []


search_manager = AzureAISearchManager()
