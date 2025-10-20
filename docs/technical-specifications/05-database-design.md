# Database Design - JIRA Triage Agent Platform

**Document Version:** 1.0  
**Last Updated:** October 20, 2025  
**Database Systems:** Azure Cosmos DB, Azure AI Search, In-Memory Queues

---

## Executive Summary

This document details the database design for the JIRA Triage Agent Platform, covering three primary data stores:
1. **Azure Cosmos DB:** Immutable decision logs (7-year retention)
2. **Azure AI Search:** Vector database for RAG knowledge base
3. **Azure Service Bus:** Message queues for async communication (development: in-memory)

The design prioritizes data governance, compliance, and auditability while maintaining high performance for real-time ticket processing.

---

## 1. Azure Cosmos DB Design

### 1.1 Database Overview

**Database Name:** `JiraTriageDB`  
**API Type:** NoSQL (Document/JSON)  
**Consistency Level:** Session (default)  
**Geo-Replication:** Multi-region (East US 2 primary, West US 2 secondary)  
**Backup Strategy:** Continuous (30-day retention)

### 1.2 Container: DecisionLogs

**Purpose:** Store immutable audit trail of all ticket triage decisions

**Partition Strategy:**
- **Partition Key:** `/ticketId`
- **Rationale:** Evenly distributes load across tickets, enables efficient queries by ticket ID

**Throughput:**
- **Mode:** Autoscale
- **Min RU/s:** 400
- **Max RU/s:** 4000
- **Estimated Cost:** ~$30/month at average load

#### 1.2.1 Document Schema

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "ticketId": "PROJ-123",
  "timestamp": "2025-10-20T10:30:45.123Z",
  "eventType": "ticket_processed",
  
  "originalTicket": {
    "summary": "Database connection timeout",
    "description": "Cannot connect to staging database - timeout after 30 seconds",
    "issueType": "Bug",
    "priority": "High",
    "reporterEmail": "john@company.com",
    "createdAt": "2025-10-20T10:00:00Z"
  },
  
  "redactionInfo": {
    "redactedEntities": [
      {
        "entityType": "EMAIL_ADDRESS",
        "startPosition": 45,
        "endPosition": 65,
        "originalText": "<REDACTED>",
        "replacementText": "<EMAIL_ADDRESS>"
      }
    ],
    "hasRedactions": true
  },
  
  "aiClassification": {
    "department": "IT-DBA",
    "assigneeId": "user-dba-lead",
    "confidence": 0.92,
    "justification": "This ticket should be assigned to IT-DBA because...",
    "modelVersion": "gpt-4-turbo-2024-04-09",
    "knowledgeBaseCitations": [
      {
        "articleId": "kb-001",
        "title": "Troubleshooting Database Timeouts",
        "url": "https://confluence.company.com/display/IT/DB-Timeouts",
        "source": "Confluence",
        "relevanceScore": 0.95
      }
    ],
    "processingLatencySeconds": 3.2
  },
  
  "policyDecision": {
    "shouldAutoAssign": true,
    "reason": "All policy checks passed",
    "confidenceThreshold": 0.7,
    "externalEmailDetected": false,
    "slaDeadline": "2025-10-20T14:00:00Z",
    "estimatedResolutionTime": "2025-10-20T12:30:00Z"
  },
  
  "humanOverride": {
    "occurred": false,
    "reviewerId": null,
    "finalDepartment": null,
    "overrideReason": null,
    "overrideTimestamp": null
  },
  
  "jiraUpdate": {
    "updateSuccessful": true,
    "assignedTo": "user-dba-lead",
    "labelsAdded": ["IT-DBA", "ai-triaged"],
    "commentAdded": true,
    "updateTimestamp": "2025-10-20T10:31:15Z"
  },
  
  "metadata": {
    "workflowVersion": "1.0.0",
    "controlPlaneVersion": ".NET 8.0",
    "reasoningPlaneVersion": "Python 3.11",
    "environmentType": "production"
  }
}
```

#### 1.2.2 Index Policy

```json
{
  "indexingMode": "consistent",
  "automatic": true,
  "includedPaths": [
    {
      "path": "/ticketId/*"
    },
    {
      "path": "/timestamp/*"
    },
    {
      "path": "/aiClassification/department/*"
    },
    {
      "path": "/policyDecision/shouldAutoAssign/*"
    },
    {
      "path": "/humanOverride/occurred/*"
    }
  ],
  "excludedPaths": [
    {
      "path": "/originalTicket/description/*"
    },
    {
      "path": "/aiClassification/justification/*"
    }
  ]
}
```

**Rationale for Exclusions:**
- Large text fields (description, justification) rarely queried directly
- Excluding reduces index size and RU consumption

#### 1.2.3 Common Queries

**Query 1: Get decision log for specific ticket**
```sql
SELECT * FROM c 
WHERE c.ticketId = "PROJ-123" 
ORDER BY c.timestamp DESC
```
**RU Cost:** ~3 RUs (using partition key)

**Query 2: Get all tickets requiring human override**
```sql
SELECT c.ticketId, c.timestamp, c.policyDecision.reason 
FROM c 
WHERE c.policyDecision.shouldAutoAssign = false 
  AND c.humanOverride.occurred = false
ORDER BY c.timestamp DESC
```
**RU Cost:** ~50-100 RUs (cross-partition query, use only for dashboard)

**Query 3: Get classification accuracy for specific department**
```sql
SELECT c.aiClassification.department, c.humanOverride.occurred, c.humanOverride.finalDepartment
FROM c
WHERE c.aiClassification.department = "IT-DBA"
  AND c.timestamp >= "2025-10-01T00:00:00Z"
```
**RU Cost:** ~75 RUs (cross-partition, time-range filter)

**Query 4: Get tickets processed in last 24 hours**
```sql
SELECT c.ticketId, c.aiClassification.department, c.aiClassification.confidence
FROM c
WHERE c.timestamp >= "2025-10-19T10:00:00Z"
ORDER BY c.timestamp DESC
```
**RU Cost:** ~100 RUs (cross-partition, time-range scan)

#### 1.2.4 Time-to-Live (TTL) Policy

**Setting:** 7 years (220,752,000 seconds)

**Configuration:**
```json
{
  "defaultTtl": 220752000
}
```

**Rationale:** Compliance requirement (SOC 2, audit trails)

---

### 1.3 Container: PendingReviews (Future)

**Purpose:** Store tickets flagged for human review

**Partition Key:** `/department`

**Document Schema:**
```json
{
  "id": "guid",
  "ticketId": "PROJ-123",
  "department": "IT-DBA",
  "aiConfidence": 0.65,
  "flagReason": "Low confidence (65% < 70%)",
  "reviewStatus": "pending",  // "pending", "approved", "overridden"
  "assignedReviewer": "user-reviewer-01",
  "createdAt": "2025-10-20T10:30:00Z",
  "ttl": 2592000  // 30 days
}
```

**TTL:** 30 days (auto-delete after review or expiry)

---

## 2. Azure AI Search Design

### 2.1 Index Overview

**Index Name:** `ticket-knowledge-base`  
**Service Tier:** Standard S1  
**Replicas:** 2 (high availability)  
**Partitions:** 1  
**Documents:** ~10,000 KB articles  
**Storage:** ~5 GB

### 2.2 Index Schema

```json
{
  "name": "ticket-knowledge-base",
  "fields": [
    {
      "name": "id",
      "type": "Edm.String",
      "key": true,
      "searchable": false,
      "filterable": false,
      "sortable": false
    },
    {
      "name": "title",
      "type": "Edm.String",
      "searchable": true,
      "filterable": false,
      "sortable": false,
      "analyzer": "en.microsoft"
    },
    {
      "name": "content",
      "type": "Edm.String",
      "searchable": true,
      "filterable": false,
      "sortable": false,
      "analyzer": "en.microsoft"
    },
    {
      "name": "embedding",
      "type": "Collection(Edm.Single)",
      "searchable": true,
      "dimensions": 1536,
      "vectorSearchProfile": "hnsw-profile"
    },
    {
      "name": "department",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "facetable": true
    },
    {
      "name": "source",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "facetable": true
    },
    {
      "name": "url",
      "type": "Edm.String",
      "searchable": false,
      "filterable": false,
      "sortable": false
    },
    {
      "name": "lastModified",
      "type": "Edm.DateTimeOffset",
      "searchable": false,
      "filterable": true,
      "sortable": true
    },
    {
      "name": "permissions",
      "type": "Collection(Edm.String)",
      "searchable": false,
      "filterable": true
    }
  ],
  "vectorSearch": {
    "profiles": [
      {
        "name": "hnsw-profile",
        "algorithm": "hnsw",
        "vectorizer": null
      }
    ],
    "algorithms": [
      {
        "name": "hnsw",
        "kind": "hnsw",
        "hnswParameters": {
          "m": 4,
          "efConstruction": 400,
          "efSearch": 500,
          "metric": "cosine"
        }
      }
    ]
  },
  "semantic": {
    "configurations": [
      {
        "name": "semantic-config",
        "prioritizedFields": {
          "titleField": {
            "fieldName": "title"
          },
          "contentFields": [
            {
              "fieldName": "content"
            }
          ]
        }
      }
    ]
  }
}
```

### 2.3 Sample Document

```json
{
  "id": "confluence-kb-001",
  "title": "Troubleshooting Database Connection Timeouts",
  "content": "When experiencing database connection timeouts, check the following: 1. Network connectivity between application and database server. 2. Database server resource utilization (CPU, memory). 3. Connection pool configuration (max connections, timeout settings). 4. Firewall rules allowing traffic on database port. Common causes: Insufficient connection pool size, network latency, authentication failures, resource contention on database server.",
  "embedding": [0.023, -0.015, 0.089, ...],  // 1536 dimensions
  "department": "IT-DBA",
  "source": "Confluence",
  "url": "https://confluence.company.com/display/IT/DB-Connection-Timeouts",
  "lastModified": "2025-09-15T14:30:00Z",
  "permissions": ["IT-DBA", "IT-DevOps", "IT-Admin"]
}
```

### 2.4 Search Queries

#### 2.4.1 Hybrid Search (Vector + Keyword)

```python
from azure.search.documents.models import VectorizedQuery

vector_query = VectorizedQuery(
    vector=query_embedding,  # 1536-dimensional vector
    k_nearest_neighbors=5,
    fields="embedding"
)

results = search_client.search(
    search_text="database timeout connection",
    vector_queries=[vector_query],
    filter="department eq 'IT-DBA'",
    select=["id", "title", "content", "url", "source"],
    top=5,
    query_type="semantic",
    semantic_configuration_name="semantic-config"
)
```

**Query Explanation:**
1. **Keyword Search:** BM25 algorithm on `title` and `content` fields
2. **Vector Search:** Cosine similarity on `embedding` field (HNSW algorithm)
3. **Semantic Ranking:** Azure's semantic ranker reorders results
4. **Filter:** Restrict to specific department

**Typical Latency:** 50-150ms (P95)

#### 2.4.2 Faceted Search (Department Breakdown)

```python
results = search_client.search(
    search_text="timeout",
    facets=["department", "source"],
    top=0  # Only get facet counts
)

# Results:
# {
#   "department": {"IT-DBA": 45, "IT-DevOps": 12, "IT-Security": 8},
#   "source": {"Confluence": 50, "SharePoint": 15}
# }
```

---

## 3. Azure Service Bus Design

### 3.1 Queue Overview

**Namespace:** `jiratriage-servicebus`  
**Tier:** Premium (VNet integration, higher throughput)  
**Region:** East US 2

### 3.2 Queue: sanitized-tickets

**Purpose:** Sanitized tickets from .NET Webhook → Python Agent

**Configuration:**
```json
{
  "maxSizeInMegabytes": 5120,
  "defaultMessageTimeToLive": "PT1H",
  "lockDuration": "PT5M",
  "maxDeliveryCount": 5,
  "enableDeadLetteringOnMessageExpiration": true,
  "enablePartitioning": true,
  "requiresDuplicateDetection": false
}
```

**Message Schema:**
```json
{
  "ticketId": "PROJ-123",
  "summary": "Database connection timeout",
  "description": "Cannot connect to staging database",
  "metadata": {
    "issueType": "Bug",
    "priority": "High",
    "reporterEmail": "john@company.com",
    "createdAt": "2025-10-20T10:00:00Z"
  },
  "redactedEntities": [
    {"entityType": "EMAIL_ADDRESS", "start": 45, "end": 65}
  ]
}
```

**Message Properties:**
```json
{
  "MessageId": "guid",
  "CorrelationId": "trace-id-from-webhook",
  "ContentType": "application/json",
  "TimeToLive": "PT1H",
  "ScheduledEnqueueTimeUtc": null
}
```

**Throughput:** ~1000 messages/hour (average)

### 3.3 Queue: enriched-tickets

**Purpose:** Enriched tickets from Python Agent → .NET Worker

**Configuration:** Same as `sanitized-tickets`

**Message Schema:**
```json
{
  "ticketId": "PROJ-123",
  "department": "IT-DBA",
  "assigneeId": "user-dba-lead",
  "confidence": 0.92,
  "justification": "This ticket should be assigned to IT-DBA because...",
  "knowledgeBaseCitations": [
    {
      "title": "Troubleshooting Database Timeouts",
      "url": "https://confluence.company.com/display/IT/DB-Timeouts",
      "source": "Confluence",
      "relevanceScore": 0.95
    }
  ],
  "estimatedSlaDeadline": "2025-10-20T14:00:00Z",
  "processingTimeSeconds": 3.2
}
```

### 3.4 Dead Letter Queue Handling

**Trigger Conditions:**
- Message delivery count > 5 (failed processing)
- Message expires before processing (TTL exceeded)
- Explicit dead-lettering by application code

**Monitoring:**
- Alert when dead letter queue depth > 10
- Daily review of dead-lettered messages
- Manual reprocessing or escalation to engineering

---

## 4. In-Memory Data Structures (Development)

### 4.1 In-Memory Queue (.NET)

**Implementation:** `System.Collections.Concurrent.BlockingCollection<T>`

```csharp
public class InMemoryQueue<T>
{
    private readonly BlockingCollection<T> _queue = new(boundedCapacity: 1000);
    
    public void Enqueue(T message)
    {
        if (!_queue.TryAdd(message, TimeSpan.FromSeconds(5)))
        {
            throw new InvalidOperationException("Queue is full");
        }
    }
    
    public T Dequeue(CancellationToken cancellationToken)
    {
        return _queue.Take(cancellationToken);
    }
}
```

**Limitation:** Data lost on application restart (no persistence)

---

## 5. Data Retention & Compliance

### 5.1 Retention Policies

| Data Type | Retention Period | Storage | Rationale |
|-----------|------------------|---------|-----------|
| **Decision Logs** | 7 years | Cosmos DB | SOC 2 compliance, legal discovery |
| **Pending Reviews** | 30 days | Cosmos DB | Short-lived operational data |
| **KB Article Index** | Until deleted | AI Search | Active knowledge base |
| **Queue Messages** | 1 hour | Service Bus | Transient processing data |
| **Application Logs** | 90 days | App Insights | Cost optimization |

### 5.2 GDPR Compliance

**Right to Access:**
```sql
-- Query all data for specific user
SELECT * FROM c 
WHERE c.originalTicket.reporterEmail = "user@example.com"
  OR c.humanOverride.reviewerId = "user@example.com"
```

**Right to Erasure (Manual Process):**
1. Query Cosmos DB for user's data
2. Export to audit file
3. Delete documents (requires manual approval)
4. Log deletion event in separate audit trail

**Data Minimization:**
- Only store necessary fields (no full JIRA attachments)
- Redact PII before storage (email → `<EMAIL_ADDRESS>`)
- Exclude large text from indexes (reduce storage footprint)

---

## 6. Backup & Disaster Recovery

### 6.1 Cosmos DB Backup

**Mode:** Continuous Backup  
**Retention:** 30 days  
**Point-in-Time Restore:** Yes (any point within 30 days)

**Restore Procedure:**
```bash
# Restore to specific timestamp
az cosmosdb sql container restore \
  --account-name jiratriage-cosmos \
  --database-name JiraTriageDB \
  --name DecisionLogs \
  --restore-timestamp "2025-10-15T14:00:00Z"
```

### 6.2 AI Search Backup

**Method:** Daily index snapshot via Azure Blob Storage

**Process:**
1. Export index documents to JSON (Azure Data Factory pipeline)
2. Store in Blob Storage (geo-redundant)
3. Retention: 7 daily snapshots

**Restore Procedure:**
1. Create new index with same schema
2. Bulk import documents from JSON snapshot
3. Rebuild vector embeddings (if needed)

### 6.3 Service Bus Backup

**Built-in:** Geo-disaster recovery (paired regions)  
**Manual:** Export queue configuration (Infrastructure as Code)

**No message backup:** Messages are transient (TTL: 1 hour)

---

## 7. Performance Optimization

### 7.1 Cosmos DB Optimization

**Indexing Strategy:**
- Include only frequently queried paths
- Exclude large text fields (description, justification)
- Use composite indexes for common query patterns

**Partition Strategy:**
- Partition by `ticketId` for even distribution
- Avoid hot partitions (no single ticket ID processed repeatedly)

**RU Optimization:**
- Use point reads (query by partition key) whenever possible
- Minimize cross-partition queries (dashboard only)
- Cache frequently accessed data (in-memory, 5 min TTL)

### 7.2 AI Search Optimization

**Vector Search:**
- HNSW algorithm parameters:
  - `m=4`: Balanced performance/accuracy
  - `efConstruction=400`: Build time optimization
  - `efSearch=500`: Query time optimization

**Semantic Ranking:**
- Enable only for final result reordering (not preliminary search)
- Use for top-K results (K=5) to limit compute cost

**Caching:**
- Cache embeddings for frequently searched queries (Redis)
- TTL: 1 hour (balance freshness vs. cost)

---

## 8. Monitoring & Alerts

### 8.1 Cosmos DB Metrics

**Metrics to Monitor:**
- RU/s consumption (alert if > 80% of provisioned)
- Request latency (alert if P95 > 50ms)
- Throttled requests (alert if > 1% of total)
- Storage size (alert if > 80% of limit)

**Alerts:**
```json
{
  "metric": "TotalRequestUnits",
  "threshold": 3200,  // 80% of 4000 max
  "frequency": "PT5M",
  "severity": "Warning"
}
```

### 8.2 AI Search Metrics

**Metrics to Monitor:**
- Query latency (alert if P95 > 200ms)
- Index size (alert if > 80% of tier limit)
- Queries per second (alert if > 100 QPS sustained)

### 8.3 Service Bus Metrics

**Metrics to Monitor:**
- Queue depth (alert if > 500 messages)
- Dead letter queue depth (alert if > 10 messages)
- Message age (alert if oldest message > 30 min)

---

## 9. Cost Estimation

### 9.1 Azure Cosmos DB

**Container:** DecisionLogs  
**Throughput:** 400-4000 RU/s autoscale  
**Storage:** ~100 GB (1M tickets/year × 100 KB/ticket)  
**Estimated Cost:** $240/month

### 9.2 Azure AI Search

**Tier:** Standard S1  
**Replicas:** 2  
**Storage:** 5 GB  
**Estimated Cost:** $500/month

### 9.3 Azure Service Bus

**Tier:** Premium (1 messaging unit)  
**Estimated Cost:** $677/month

**Total Database Costs:** ~$1,400/month

---

## 10. Schema Evolution Strategy

### 10.1 Cosmos DB Schema Versioning

**Approach:** Additive schema changes only

**Example Migration:**
```json
{
  "id": "guid",
  "ticketId": "PROJ-123",
  "schemaVersion": "2.0",  // New field
  "newField": "value",      // Added in v2.0
  // Existing fields remain unchanged
}
```

**Backward Compatibility:**
- Application code checks `schemaVersion` field
- Falls back to default values for missing fields
- No breaking changes (only additions)

### 10.2 AI Search Index Updates

**Approach:** Blue-green deployment

1. Create new index with updated schema (`ticket-knowledge-base-v2`)
2. Populate new index (parallel to existing)
3. Switch application to new index (config change)
4. Delete old index after validation period

---

## Appendix A: ER Diagram

```
┌─────────────────────┐
│  DecisionLogs       │
│  (Cosmos DB)        │
├─────────────────────┤
│ PK: id (GUID)       │
│ SK: ticketId        │
├─────────────────────┤
│ timestamp           │
│ originalTicket      │
│ aiClassification    │
│ policyDecision      │
│ humanOverride       │
│ jiraUpdate          │
└─────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────┐
│  PendingReviews     │
│  (Cosmos DB)        │
├─────────────────────┤
│ PK: id (GUID)       │
│ SK: department      │
├─────────────────────┤
│ ticketId (FK)       │
│ reviewStatus        │
│ assignedReviewer    │
└─────────────────────┘

┌─────────────────────┐
│  KB Articles        │
│  (AI Search)        │
├─────────────────────┤
│ PK: id              │
├─────────────────────┤
│ title               │
│ content             │
│ embedding           │
│ department          │
│ source              │
└─────────────────────┘
```

---

## Appendix B: Sample Data

**Sample DecisionLog Document (Full):**
See Section 1.2.1 for complete schema

**Sample KB Article (Full):**
See Section 2.3 for complete example

---

**Document Control:**
- **Classification:** Internal Database Documentation
- **Distribution:** Engineering, DBAs, Data Architects
- **Review Schedule:** Quarterly
- **Version:** 1.0 (2025-10-20)
