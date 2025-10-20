# High-Level Design (HLD) - JIRA Triage Agent Platform

**Document Version:** 1.0  
**Last Updated:** October 20, 2025  
**Architecture Style:** Hybrid Polyglot with Clean Boundaries

---

## Executive Summary

This document presents the High-Level Design (HLD) for the JIRA Triage Agent Platform, an enterprise-grade GenAI-powered system that automates JIRA ticket triage while maintaining human oversight. The architecture implements a **Hybrid Polyglot** approach, combining .NET 8 for enterprise control plane operations with Python 3.11 for AI reasoning, connected via asynchronous messaging to ensure zero-trust data governance.

---

## 1. System Architecture Overview

### 1.1 Architectural Style

**Pattern:** Hybrid Polyglot Microservices with Event-Driven Architecture

**Core Principles:**
1. **Separation of Concerns:** Control plane (.NET) handles data governance, reasoning plane (Python) handles AI logic
2. **Async Communication:** Services communicate via Azure Service Bus (development: in-memory queues)
3. **Zero-Trust Security:** Sensitive data never leaves .NET boundary
4. **Immutable Audit Trail:** All decisions logged to append-only Cosmos DB
5. **Vertical Slicing:** Department-specific agent configurations (IT, HR, Finance, etc.)

### 1.2 System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    JIRA Triage Agent Platform                       │
│                                                                     │
│  ┌──────────────────┐         ┌──────────────────────┐            │
│  │  Control Plane   │ <-----> │  Reasoning Plane     │            │
│  │    (.NET 8)      │  Queue  │    (Python 3.11)     │            │
│  │                  │         │                      │            │
│  │  - DLP Redaction │         │  - LangGraph Agents  │            │
│  │  - Policy Engine │         │  - RAG Retrieval     │            │
│  │  - Human Review  │         │  - LLM Classification│            │
│  └──────────────────┘         └──────────────────────┘            │
│          │                              │                          │
│          └──────────────┬───────────────┘                          │
└───────────────────────────────────────────────────────────────────┘
                          │
    ┌─────────────────────┼─────────────────────┐
    │                     │                     │
    ▼                     ▼                     ▼
┌─────────┐         ┌──────────┐         ┌─────────┐
│  JIRA   │         │  Azure   │         │  Azure  │
│  Cloud  │         │  OpenAI  │         │ Cosmos  │
│   API   │         │   GPT-4  │         │   DB    │
└─────────┘         └──────────┘         └─────────┘
```

### 1.3 High-Level Component Diagram

```
┌────────────────────────── CONTROL PLANE (.NET 8) ──────────────────────────┐
│                                                                             │
│  ┌─────────────────┐      ┌─────────────────┐      ┌──────────────────┐  │
│  │ JiraTriage.     │      │ JiraTriage.     │      │ JiraTriage.      │  │
│  │ Webhook API     │      │ Worker          │      │ UI               │  │
│  │ (Port 5001)     │      │ (Background)    │      │ (Port 5000)      │  │
│  ├─────────────────┤      ├─────────────────┤      ├──────────────────┤  │
│  │ - Receive       │      │ - Consume       │      │ - Razor Pages    │  │
│  │   webhook       │      │   enriched      │      │ - Pending Review │  │
│  │ - Validate      │      │   tickets       │      │ - Approve/       │  │
│  │   signature     │      │ - Apply policy  │      │   Override UI    │  │
│  │ - Fetch from    │      │ - Update JIRA   │      │ - Analytics      │  │
│  │   JIRA API      │      │   or flag       │      │   Dashboard      │  │
│  │ - Redact PII    │      │   for review    │      │                  │  │
│  │   (Presidio)    │      │ - Log decision  │      │                  │  │
│  │ - Publish to    │      │                 │      │                  │  │
│  │   queue         │      │                 │      │                  │  │
│  └─────────────────┘      └─────────────────┘      └──────────────────┘  │
│           │                        ▲                        ▲             │
└───────────┼────────────────────────┼────────────────────────┼─────────────┘
            │                        │                        │
            ▼                        │                        │
    ┌──────────────────┐            │                        │
    │ Service Bus      │            │                        │
    │ Queue:           │            │                        │
    │ sanitized-       │            │                        │
    │ tickets          │            │                        │
    └──────────────────┘            │                        │
            │                        │                        │
            ▼                        │                        │
┌───────────────────────── REASONING PLANE (Python) ─────────────────────────┐
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │              FastAPI Service (Port 8001)                            │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │                  LangGraph Agent Workflow                     │  │  │
│  │  │                                                               │  │  │
│  │  │  ┌───────────┐   ┌────────────┐   ┌────────────┐   ┌──────┐ │  │  │
│  │  │  │ Classify  │ → │  Retrieve  │ → │  Generate  │ → │Policy│ │  │  │
│  │  │  │   Node    │   │    Node    │   │    Node    │   │ Node │ │  │  │
│  │  │  └───────────┘   └────────────┘   └────────────┘   └──────┘ │  │  │
│  │  │       │                │                 │              │    │  │  │
│  │  │       ▼                ▼                 ▼              ▼    │  │  │
│  │  │   Department      KB Articles        Justification   Pass/  │  │  │
│  │  │   Assignment      (RAG)              + Citations      Fail  │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                  │                                         │
│                                  ▼                                         │
│                        ┌──────────────────┐                                │
│                        │ Service Bus      │                                │
│                        │ Queue:           │                                │
│                        │ enriched-        │                                │
│                        │ tickets          │                                │
│                        └──────────────────┘                                │
│                                  │                                         │
└───────────────────────────────────┼─────────────────────────────────────────┘
                                    │
                                    └──────────────► (Back to Worker)
```

---

## 2. Component Architecture

### 2.1 Control Plane Components (.NET 8)

#### 2.1.1 JiraTriage.Webhook (Minimal API)

**Purpose:** Webhook ingestion endpoint for JIRA issue_created events

**Responsibilities:**
- HTTP endpoint: `POST /api/webhook`
- Validate webhook signature (HMAC-SHA256)
- Authenticate request (IP whitelist + JWT)
- Fetch full issue details from JIRA REST API
- Redact PII using Presidio (.NET wrapper via Python bridge)
- Publish sanitized ticket to Service Bus queue

**Key Technologies:**
- ASP.NET Core Minimal API (HTTP server)
- System.Text.Json (JSON serialization)
- Azure.Messaging.ServiceBus (queue publishing)
- HttpClient (JIRA API calls)

**Interfaces:**
```csharp
// Input
public record WebhookRequest(string WebhookEvent, long Timestamp, JiraIssue Issue);

// Output
public record SanitizedTicket(
    string TicketId,
    string Summary,         // PII redacted
    string Description,     // PII redacted
    List<RedactionFlag> RedactedEntities,
    TicketMetadata Metadata
);
```

**Deployment:**
- Port: 5001
- Scaling: Horizontal (multi-instance with load balancer)
- Health Check: `/health` endpoint (checks JIRA API + Service Bus)

#### 2.1.2 JiraTriage.Worker (Background Service)

**Purpose:** Process enriched tickets and enforce business policies

**Responsibilities:**
- Consume enriched tickets from Service Bus queue
- Apply policy rules:
  - Confidence threshold check (≥ 0.7 for auto-assignment)
  - External email detection (always flag for review)
  - SLA prediction (escalate if predicted > deadline)
- Auto-assign: Update JIRA issue via REST API
- Manual review: Store in database for UI display
- Log all decisions to Cosmos DB (immutable audit trail)

**Key Technologies:**
- IHostedService (background processing)
- Azure.Messaging.ServiceBus (queue consumption)
- Azure.Cosmos (decision log storage)
- HttpClient (JIRA API updates)

**Interfaces:**
```csharp
// Input
public record EnrichedTicket(
    string TicketId,
    string Department,       // e.g., "IT-DBA"
    string AssigneeId,
    double Confidence,       // 0.0 - 1.0
    string Justification,
    List<Citation> KnowledgeBaseCitations,
    DateTime EstimatedSlaDeadline
);

// Output (to JIRA)
public record JiraUpdate(
    string AssigneeAccountId,
    List<string> Labels,
    string Comment  // AI justification
);
```

**Deployment:**
- Instances: 3 (active-active for high availability)
- Queue Processing: 100 messages/second total throughput
- Retry Policy: Exponential backoff (max 5 retries)

#### 2.1.3 JiraTriage.UI (Razor Pages)

**Purpose:** Human-in-the-loop review dashboard

**Responsibilities:**
- Display pending review queue (sorted by priority)
- Show ticket details (original + AI recommendation)
- Approve/Override/Reassign actions
- Analytics dashboard (classification accuracy, SLA compliance)
- User authentication (Azure AD SSO)

**Key Technologies:**
- ASP.NET Core Razor Pages (server-side rendering)
- Bootstrap 5 (responsive UI)
- jQuery (AJAX interactions)
- SignalR (real-time updates - future)

**Pages:**
```
/                   - Dashboard (metrics summary)
/PendingReviews     - Queue of flagged tickets
/TicketDetail/{id}  - Detailed ticket view with approval UI
/Analytics          - Historical performance metrics
/Admin/Config       - Policy configuration (admin only)
```

**Deployment:**
- Port: 5000
- Scaling: Horizontal with session affinity (sticky sessions)
- Cache: In-memory cache for ticket metadata (5 min TTL)

#### 2.1.4 JiraTriage.Core (Shared Library)

**Purpose:** Shared domain models and utilities

**Components:**
- Domain models (Ticket, User, Decision, etc.)
- DLP engine wrapper (calls Python Presidio service)
- Policy engine (confidence threshold, SLA rules)
- Validation logic (webhook signature verification)

**No deployment** (library referenced by all .NET projects)

---

### 2.2 Reasoning Plane Components (Python 3.11)

#### 2.2.1 FastAPI Service

**Purpose:** HTTP endpoint for ticket processing

**Responsibilities:**
- HTTP endpoint: `POST /agent/process`
- Invoke LangGraph workflow
- Return enriched ticket response
- Handle errors (LLM API failures, timeouts)

**Key Technologies:**
- FastAPI (async web framework)
- Uvicorn (ASGI server)
- Pydantic (request/response validation)

**Endpoints:**
```python
@app.post("/agent/process")
async def process_ticket(request: TicketRequest) -> TicketResponse:
    # Invoke LangGraph workflow
    pass

@app.get("/health")
async def health_check() -> dict:
    # Check Azure OpenAI, AI Search connectivity
    pass
```

**Deployment:**
- Port: 8001
- Scaling: Vertical (4 vCPU, 8 GB RAM per instance)
- Workers: 4 Uvicorn workers per instance
- Timeout: 30 seconds per request

#### 2.2.2 LangGraph Agent Workflow

**Purpose:** Multi-agent ticket classification pipeline

**Nodes:**

1. **ClassifyNode:**
   - Input: Sanitized ticket (summary, description)
   - Process: LLM prompt with few-shot examples
   - Output: Department assignment + confidence score

2. **RetrieveNode:**
   - Input: Ticket + department assignment
   - Process: Azure AI Search (vector + keyword hybrid search)
   - Output: Top-5 relevant KB articles

3. **GenerateNode:**
   - Input: Ticket + KB articles
   - Process: LLM prompt with RAG context
   - Output: Justification text with citations

4. **PolicyNode:**
   - Input: Full enrichment result
   - Process: Validate confidence threshold, business rules
   - Output: Pass/Fail decision

**Key Technologies:**
- LangGraph (workflow orchestration)
- LangChain (LLM abstraction)
- Azure OpenAI (GPT-4, embeddings)

**State Graph:**
```
START → ClassifyNode → RetrieveNode → GenerateNode → PolicyNode → END
         │              │               │              │
         ▼              ▼               ▼              ▼
    Dept + Conf    KB Articles    Justification   Pass/Fail
```

**Deployment:**
- Stateless (no persistence between requests)
- Timeout: 25 seconds (5 sec buffer for FastAPI)

#### 2.2.3 Vertical Slices (Department-Specific Agents)

**Purpose:** Customized agent configurations per department

**Slices:**
- **IT Support:** Sub-teams (DBA, DevOps, Security, Networking)
- **HR:** Sub-teams (Onboarding, Payroll, Benefits, Offboarding)
- **Finance:** Sub-teams (AP, AR, Budgeting, Compliance)
- **Legal:** Sub-teams (Contracts, IP, Compliance, Litigation)

**Configuration:**
```python
vertical_slices = {
    "IT-DBA": {
        "llm_config": {"temperature": 0.2, "max_tokens": 500},
        "kb_filter": {"spaces": ["IT-DBA-KB"]},
        "confidence_threshold": 0.75  # Higher threshold for critical systems
    },
    "HR-Onboarding": {
        "llm_config": {"temperature": 0.5, "max_tokens": 800},
        "kb_filter": {"spaces": ["HR-Onboarding"]},
        "confidence_threshold": 0.65  # Lower threshold for routine tasks
    }
}
```

**Deployment:**
- Single Python service, slice selected based on initial classification
- Future: Separate deployment per vertical for scaling

#### 2.2.4 Connectors (Knowledge Base Integration)

**Confluence Connector:**
- API: Confluence Cloud REST API v2
- Authentication: API token
- Operations: CQL search, fetch article body
- Rate Limit: 100 requests/minute

**SharePoint Connector:**
- API: Microsoft Graph API
- Authentication: Azure AD app registration (client credentials)
- Operations: Document search, download content
- Rate Limit: 10,000 requests/hour

**Deployment:**
- Singleton pattern (shared across all requests)
- Connection pooling for HTTP clients
- Retry logic: 3 retries with exponential backoff

---

## 3. Data Flow Architecture

### 3.1 End-to-End Happy Path

```
┌──────────┐
│  JIRA    │  1. Webhook: issue_created event
│  Cloud   │ ────────────────────────────────────┐
└──────────┘                                     │
                                                 ▼
                                   ┌──────────────────────────┐
                                   │ JiraTriage.Webhook API   │
                                   │ - Validate signature     │
                                   │ - Fetch full issue       │
                                   │ - Redact PII (Presidio)  │
                                   └──────────────────────────┘
                                                 │
                                                 │ 2. Publish sanitized ticket
                                                 ▼
                                   ┌──────────────────────────┐
                                   │ Service Bus Queue        │
                                   │ "sanitized-tickets"      │
                                   └──────────────────────────┘
                                                 │
                                                 │ 3. Consume ticket
                                                 ▼
                                   ┌──────────────────────────┐
                                   │ Python FastAPI Agent     │
                                   │ LangGraph Workflow:      │
                                   │  - Classify (GPT-4)      │
                                   │  - Retrieve (AI Search)  │
                                   │  - Generate (GPT-4)      │
                                   │  - Policy Check          │
                                   └──────────────────────────┘
                                                 │
                                                 │ 4. Publish enriched ticket
                                                 ▼
                                   ┌──────────────────────────┐
                                   │ Service Bus Queue        │
                                   │ "enriched-tickets"       │
                                   └──────────────────────────┘
                                                 │
                                                 │ 5. Consume enriched
                                                 ▼
                                   ┌──────────────────────────┐
                                   │ JiraTriage.Worker        │
                                   │ - Apply policy rules     │
                                   │ - Decision: Auto/Review  │
                                   └──────────────────────────┘
                                                 │
                         ┌───────────────────────┼───────────────────────┐
                         │                       │                       │
                 (Confidence ≥ 0.7)      (Confidence < 0.7)              │
                 & Internal Email         OR External Email              │
                         │                       │                       │
                         ▼                       ▼                       ▼
              ┌───────────────────┐   ┌──────────────────┐   ┌──────────────┐
              │  Update JIRA      │   │  Flag for Review │   │  Log Decision│
              │  - Set assignee   │   │  - Store in DB   │   │  (Cosmos DB) │
              │  - Add comment    │   │  - Notify user   │   │  - Immutable │
              └───────────────────┘   └──────────────────┘   └──────────────┘
                         │                       │
                         └───────────────────────┘
                                     │
                                     │ 6. Human review (if needed)
                                     ▼
                              ┌──────────────────┐
                              │ JiraTriage.UI    │
                              │ - Approve/       │
                              │   Override       │
                              │ - Update JIRA    │
                              └──────────────────┘
```

### 3.2 Error Handling Flow

**LLM API Failure:**
```
Python Agent → Azure OpenAI (500 error)
  ↓
Retry (3 attempts with exponential backoff)
  ↓
If all retries fail:
  - Log error to Application Insights
  - Send ticket to dead letter queue
  - Alert on-call engineer (PagerDuty)
```

**JIRA API Failure:**
```
Worker → JIRA API (429 rate limit exceeded)
  ↓
Back off for 60 seconds
  ↓
Retry update
  ↓
If still failing:
  - Store pending update in database
  - Retry via scheduled job (every 5 min)
```

---

## 4. Integration Architecture

### 4.1 External System Integrations

#### 4.1.1 JIRA Cloud Integration

**Direction:** Bidirectional

**Inbound (Webhook):**
- Endpoint: `POST /api/webhook`
- Payload: JIRA issue_created event
- Authentication: Webhook secret (HMAC-SHA256 signature)

**Outbound (REST API):**
- Operations:
  - `GET /rest/api/3/issue/{issueKey}` - Fetch issue details
  - `PUT /rest/api/3/issue/{issueKey}` - Update assignee, labels
  - `POST /rest/api/3/issue/{issueKey}/comment` - Add AI comment
- Authentication: API token (stored in Azure Key Vault)
- Rate Limit: 1000 requests/hour (managed via queue throttling)

#### 4.1.2 Azure OpenAI Integration

**Direction:** Outbound only

**Endpoints:**
- `POST /deployments/gpt-4-turbo/chat/completions` - Classification & reasoning
- `POST /deployments/text-embedding-3-small/embeddings` - Vector generation

**Authentication:** 
- Development: API key
- Production: Managed Identity (Azure AD)

**Rate Limits:**
- 60,000 tokens/minute (standard deployment)
- Mitigation: Request queuing + backpressure

#### 4.1.3 Azure AI Search Integration

**Direction:** Outbound only

**Operations:**
- Vector search (1536-dimensional embeddings)
- Hybrid search (vector + keyword BM25)
- Semantic ranking

**Index Schema:**
```json
{
  "name": "ticket-knowledge-base",
  "fields": [
    {"name": "id", "type": "Edm.String", "key": true},
    {"name": "title", "type": "Edm.String", "searchable": true},
    {"name": "content", "type": "Edm.String", "searchable": true},
    {"name": "embedding", "type": "Collection(Edm.Single)", "dimensions": 1536},
    {"name": "source", "type": "Edm.String"},  // "Confluence", "SharePoint"
    {"name": "url", "type": "Edm.String"}
  ]
}
```

#### 4.1.4 Azure Cosmos DB Integration

**Direction:** Outbound only (write-heavy)

**Container:** `DecisionLogs`

**Partition Key:** `/ticketId`

**Document Schema:**
```json
{
  "id": "unique-guid",
  "ticketId": "PROJ-123",
  "timestamp": "2025-10-20T10:30:00Z",
  "originalTicket": { /* sanitized */ },
  "aiClassification": {
    "department": "IT-DBA",
    "confidence": 0.85,
    "justification": "...",
    "citations": [...]
  },
  "humanOverride": {
    "reviewerId": "user@company.com",
    "finalDepartment": "IT-DevOps",
    "reason": "Better fit for DevOps team",
    "timestamp": "2025-10-20T11:00:00Z"
  },
  "processingLatency": 12.5  // seconds
}
```

---

## 5. Security Architecture

### 5.1 Authentication & Authorization

**UI Dashboard:**
- Authentication: Azure AD (OAuth 2.0)
- Authorization: RBAC (Reviewer, Manager, Admin roles)
- Session Management: ASP.NET Core Identity with cookie auth

**Webhook API:**
- Authentication: HMAC-SHA256 signature validation
- IP Whitelist: JIRA Cloud IP ranges (configured in App Service)

**Azure Services:**
- Managed Identity: .NET services use DefaultAzureCredential
- Python services: Service principal (client credentials flow)

### 5.2 Data Protection

**Encryption in Transit:**
- TLS 1.3 for all HTTP traffic
- Azure App Service managed certificates
- Azure Front Door SSL termination (production)

**Encryption at Rest:**
- Azure Storage Service Encryption (SSE) - AES-256
- Cosmos DB: Transparent Data Encryption (TDE)
- Azure Key Vault: HSM-backed keys

**PII Redaction:**
- Presidio analyzer detects: email, phone, SSN, credit card, names
- Redaction strategy: Replace with entity type tag (e.g., `<EMAIL_ADDRESS>`)
- Audit: All redactions logged with position offsets

### 5.3 Secret Management

**Azure Key Vault:**
- Secrets stored:
  - JIRA API token
  - Azure OpenAI API key (dev only)
  - Service Bus connection string
  - Cosmos DB connection string
  - Webhook secret
- Access: Managed Identity for .NET, service principal for Python
- Rotation: 90-day automatic rotation (future)

---

## 6. Observability Architecture

### 6.1 Logging

**Structured Logging:**
- Format: JSON
- Destination: Azure Application Insights
- Correlation: Distributed trace IDs (W3C Trace Context)

**Log Levels:**
- **Error:** LLM API failures, JIRA update errors
- **Warning:** Low confidence classifications, policy violations
- **Info:** Ticket processing lifecycle events
- **Debug:** Detailed LLM prompts/responses (dev only)

### 6.2 Metrics

**Application Insights Metrics:**
- `tickets_processed_total` (counter)
- `classification_confidence_avg` (gauge)
- `processing_latency_seconds` (histogram)
- `jira_api_requests_total` (counter)
- `llm_api_tokens_used` (counter)

**Custom Dashboards:**
- Real-time throughput (tickets/hour)
- Average confidence score (by department)
- SLA compliance rate
- Human override rate

### 6.3 Distributed Tracing

**Trace Propagation:**
```
JIRA Webhook → .NET Webhook API [span: webhook_ingestion]
                      ↓
              Service Bus Publish [span: queue_publish]
                      ↓
              Python Agent [span: agent_processing]
                      ├─ [span: llm_classification]
                      ├─ [span: rag_retrieval]
                      └─ [span: llm_generation]
                      ↓
              Service Bus Publish [span: enriched_publish]
                      ↓
              .NET Worker [span: worker_processing]
                      └─ [span: jira_update]
```

**Tools:**
- OpenTelemetry (.NET + Python)
- Azure Application Insights (trace aggregation)

---

## 7. Scalability & Performance

### 7.1 Horizontal Scaling

| Component | Scaling Strategy | Trigger | Max Instances |
|-----------|------------------|---------|---------------|
| **Webhook API** | Azure App Service autoscale | CPU > 70% | 10 |
| **Worker** | Manual scale (future: autoscale) | Queue depth > 1000 | 10 |
| **UI Dashboard** | Autoscale with session affinity | Requests/sec > 500 | 5 |
| **Python Agent** | Container Instances autoscale | CPU > 80% | 8 |

### 7.2 Vertical Scaling

| Component | Current | Target (Production) |
|-----------|---------|---------------------|
| **Webhook API** | 1 vCPU, 1.75 GB RAM | 2 vCPU, 4 GB RAM |
| **Worker** | 1 vCPU, 1.75 GB RAM | 2 vCPU, 4 GB RAM |
| **Python Agent** | 2 vCPU, 4 GB RAM | 4 vCPU, 8 GB RAM |

### 7.3 Caching Strategy

**In-Memory Cache (.NET):**
- JIRA user profiles (5 min TTL)
- Department configurations (30 min TTL)
- Knowledge base article metadata (15 min TTL)

**Redis Cache (Future):**
- LLM response cache (same ticket description → same result)
- Vector embeddings cache (avoid re-embedding)

---

## 8. Deployment Architecture

### 8.1 Development Environment

```
┌─────────────────────────────────────────────┐
│          Replit (NixOS)                     │
│                                             │
│  ┌─────────────┐  ┌─────────────┐          │
│  │  .NET UI    │  │  Python     │          │
│  │  (Port 5000)│  │  Agent      │          │
│  │             │  │  (Port 8001)│          │
│  └─────────────┘  └─────────────┘          │
│                                             │
│  ┌─────────────────────────────┐           │
│  │  In-Memory Queues           │           │
│  │  (Development only)         │           │
│  └─────────────────────────────┘           │
└─────────────────────────────────────────────┘
```

### 8.2 Production Environment

```
                    ┌─────────────────────┐
                    │  Azure Front Door   │
                    │  (Global LB + CDN)  │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
     ┌─────────────┐  ┌──────────────┐  ┌─────────────┐
     │ App Service │  │ App Service  │  │  Container  │
     │  Webhook    │  │  UI          │  │  Instances  │
     │  (5001)     │  │  (5000)      │  │  Python     │
     │  (3 inst)   │  │  (2 inst)    │  │  (4 inst)   │
     └─────────────┘  └──────────────┘  └─────────────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Azure Service Bus  │
                    │  (Premium tier)     │
                    └─────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌─────────────┐  ┌──────────────┐  ┌─────────────┐
     │  Cosmos DB  │  │  AI Search   │  │  Key Vault  │
     │  (Multi-    │  │  (Standard)  │  │  (Secrets)  │
     │   region)   │  │              │  │             │
     └─────────────┘  └──────────────┘  └─────────────┘
```

---

## 9. Disaster Recovery Architecture

### 9.1 Backup Strategy

| Component | Backup Frequency | Retention |
|-----------|------------------|-----------|
| **Cosmos DB** | Continuous (automatic) | 30 days |
| **Azure AI Search** | Daily (index snapshot) | 7 days |
| **Application Code** | Git commits | Infinite (GitHub) |
| **Configuration** | Infrastructure as Code | Infinite (version control) |

### 9.2 Failover Strategy

**Multi-Region Deployment:**
- Primary: East US 2
- Secondary: West US 2 (read-only replicas)

**Failover Trigger:**
- Azure Front Door health probe failures (3 consecutive)
- Manual failover via Azure Portal

**RTO/RPO Targets:**
- Recovery Time Objective (RTO): 4 hours
- Recovery Point Objective (RPO): 15 minutes

---

## 10. Technology Stack Summary

| Layer | Technology |
|-------|-----------|
| **Control Plane Runtime** | .NET 8, C# 12 |
| **Reasoning Plane Runtime** | Python 3.11 |
| **Web Frameworks** | ASP.NET Core (Minimal API, Razor Pages), FastAPI |
| **AI Frameworks** | LangChain, LangGraph, Presidio |
| **LLM Provider** | Azure OpenAI (GPT-4, text-embedding-3-small) |
| **Messaging** | Azure Service Bus |
| **Database** | Azure Cosmos DB (NoSQL), Azure AI Search (Vector DB) |
| **Secret Management** | Azure Key Vault |
| **Observability** | Application Insights, OpenTelemetry |
| **Authentication** | Azure AD (Entra ID) |
| **Deployment** | Azure App Service, Azure Container Instances |

---

## Appendix A: Architecture Decision Records (ADRs)

See `docs/adr/001-hybrid-polyglot.md` for detailed architectural justifications.

**Key Decisions:**
1. **Hybrid Polyglot:** .NET for control, Python for AI (rationale: leverage best-in-class libraries)
2. **Async Messaging:** Service Bus over direct HTTP (rationale: decoupling, retry, backpressure)
3. **Immutable Audit Log:** Cosmos DB append-only (rationale: compliance, forensics)
4. **Zero-Trust Data:** PII never sent to Python (rationale: regulatory compliance)

---

## Appendix B: Component Interaction Matrix

| Component | Webhook API | Worker | UI | Python Agent | JIRA | Azure OpenAI | Cosmos DB |
|-----------|-------------|--------|----|--------------|------|--------------|-----------|
| **Webhook API** | - | Queue | - | Queue | REST | - | - |
| **Worker** | - | - | DB | - | REST | - | Write |
| **UI** | - | - | - | - | - | - | Read |
| **Python Agent** | Queue | Queue | - | - | - | REST | - |

---

**Document Control:**
- **Classification:** Internal Architecture Documentation
- **Distribution:** Engineering, Architecture Review Board
- **Review Schedule:** Quarterly
- **Next Review:** Q2 2026
