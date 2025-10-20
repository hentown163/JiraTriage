"""
Azure Cosmos DB Integration for Immutable Decision Log Storage
7-year retention policy for compliance and audit trail
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from azure.cosmos import CosmosClient, PartitionKey, exceptions
import json


class CosmosDBDecisionLogger:
    """
    Azure Cosmos DB manager for immutable decision logging
    
    Features:
    - Immutable audit trail (insert-only)
    - 7-year retention policy (2555 days TTL)
    - Partition by department for scalability
    - Point-in-time recovery enabled
    """
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        key: Optional[str] = None,
        database_name: str = "JiraTriageDB",
        container_name: str = "DecisionLogs"
    ):
        self.endpoint = endpoint or os.environ.get("COSMOS_ENDPOINT")
        self.key = key or os.environ.get("COSMOS_KEY")
        self.database_name = database_name
        self.container_name = container_name
        
        if not self.endpoint or not self.key:
            print("Warning: Azure Cosmos DB not configured. Logs will not be persisted.")
            self.configured = False
            return
        
        self.configured = True
        self.client = CosmosClient(self.endpoint, self.key)
        self.database = None
        self.container = None
        
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """
        Initialize Cosmos DB database and container with proper schema
        """
        if not self.configured:
            return
        
        try:
            self.database = self.client.create_database_if_not_exists(
                id=self.database_name
            )
            
            self.container = self.database.create_container_if_not_exists(
                id=self.container_name,
                partition_key=PartitionKey(path="/department"),
                default_ttl=2555 * 24 * 60 * 60
            )
            
            print(f"Cosmos DB '{self.database_name}' initialized successfully.")
        except exceptions.CosmosHttpResponseError as e:
            print(f"Error initializing Cosmos DB: {e}")
            self.configured = False
    
    def log_decision(
        self,
        ticket_id: str,
        issue_key: str,
        decision_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Log an immutable decision record to Cosmos DB
        
        Args:
            ticket_id: Unique ticket identifier
            issue_key: JIRA issue key (e.g., PROJ-123)
            decision_data: Complete decision payload from agent
            
        Returns:
            Decision log ID or None if not configured
        """
        if not self.configured:
            print(f"[MOCK LOG] Decision for {issue_key}: {decision_data.get('classification', {}).get('department', 'Unknown')}")
            return None
        
        timestamp = datetime.utcnow()
        decision_log = {
            "id": f"{ticket_id}_{int(timestamp.timestamp())}",
            "ticket_id": ticket_id,
            "issue_key": issue_key,
            "timestamp": timestamp.isoformat(),
            "department": decision_data.get("classification", {}).get("department", "General"),
            "team": decision_data.get("classification", {}).get("team", "Support"),
            "classification": decision_data.get("classification"),
            "generated_comment": decision_data.get("generated_comment"),
            "citations": decision_data.get("citations", []),
            "policy_flags": decision_data.get("policy_flags", []),
            "confidence": decision_data.get("confidence", 0.0),
            "model_used": decision_data.get("model_used", "unknown"),
            "requires_human_review": decision_data.get("requires_human_review", False),
            "ttl": 2555 * 24 * 60 * 60
        }
        
        try:
            result = self.container.create_item(body=decision_log)
            print(f"Decision logged: {result['id']}")
            return result['id']
        except exceptions.CosmosHttpResponseError as e:
            print(f"Error logging decision: {e}")
            return None
    
    def query_decisions(
        self,
        department: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_items: int = 100
    ) -> list[Dict[str, Any]]:
        """
        Query decision logs with filters
        
        Args:
            department: Filter by department
            start_date: Filter by start date
            end_date: Filter by end date
            max_items: Maximum number of items to return
            
        Returns:
            List of decision log records
        """
        if not self.configured:
            return []
        
        query = "SELECT * FROM c WHERE 1=1"
        parameters = []
        
        if department:
            query += " AND c.department = @department"
            parameters.append({"name": "@department", "value": department})
        
        if start_date:
            query += " AND c.timestamp >= @start_date"
            parameters.append({"name": "@start_date", "value": start_date.isoformat()})
        
        if end_date:
            query += " AND c.timestamp <= @end_date"
            parameters.append({"name": "@end_date", "value": end_date.isoformat()})
        
        query += " ORDER BY c.timestamp DESC"
        
        try:
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                max_item_count=max_items
            ))
            return items
        except exceptions.CosmosHttpResponseError as e:
            print(f"Error querying decisions: {e}")
            return []
    
    def get_decision_by_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the most recent decision for a specific ticket
        """
        if not self.configured:
            return None
        
        query = "SELECT * FROM c WHERE c.ticket_id = @ticket_id ORDER BY c.timestamp DESC"
        parameters = [{"name": "@ticket_id", "value": ticket_id}]
        
        try:
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                max_item_count=1
            ))
            return items[0] if items else None
        except exceptions.CosmosHttpResponseError as e:
            print(f"Error retrieving decision: {e}")
            return None


decision_logger = CosmosDBDecisionLogger()
