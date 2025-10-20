# Technology Stack - JIRA Triage Agent Platform

**Document Version:** 1.0  
**Last Updated:** October 20, 2025  
**Author:** Technical Architecture Team

---

## Executive Summary

The JIRA Triage Agent Platform leverages a **Hybrid Polyglot Architecture** combining enterprise-grade .NET 8 for control plane operations with Python 3.11 for AI reasoning capabilities. This document provides a comprehensive breakdown of all technologies, frameworks, libraries, and tools used across the platform.

---

## 1. Core Runtime Environments

### 1.1 .NET Control Plane

| Component | Version | Purpose |
|-----------|---------|---------|
| .NET SDK | 8.0.412 | Primary runtime for control plane services |
| ASP.NET Core | 8.0 | Web framework for HTTP APIs and UI |
| C# | 12.0 | Primary programming language |
| NuGet | 6.11+ | Package management |

**Rationale:** .NET 8 provides enterprise-grade security, performance, and reliability required for handling sensitive JIRA data, webhook processing, and policy enforcement.

### 1.2 Python Reasoning Plane

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Runtime for AI/ML workloads |
| pip/uv | Latest | Package management |
| Virtual Environment | venv | Dependency isolation |

**Rationale:** Python's rich AI/ML ecosystem (LangChain, LangGraph) and rapid development cycle make it ideal for iterative agent development.

---

## 2. Web Frameworks & APIs

### 2.1 .NET Components

#### ASP.NET Core Minimal API
- **Version:** 8.0
- **Use Case:** Webhook ingestion endpoint (JiraTriage.Webhook)
- **Key Features:**
  - High-performance HTTP request handling
  - Built-in model binding and validation
  - Middleware pipeline for cross-cutting concerns
  - Native JSON serialization (System.Text.Json)

**Sample Implementation:**
```csharp
app.MapPost("/api/webhook", async (WebhookRequest request) => 
{
    // Validation, redaction, queue publishing
    return Results.Accepted();
});
```

#### ASP.NET Core Razor Pages
- **Version:** 8.0
- **Use Case:** Human-in-the-loop review dashboard (JiraTriage.UI)
- **Key Features:**
  - Server-side rendering with MVVM pattern
  - Built-in CSRF protection
  - Tag helpers for clean HTML
  - Bootstrap 5 integration

**Sample Page:**
```cshtml
@page
@model IndexModel
<h1>Pending Reviews: @Model.PendingCount</h1>
```

#### Background Services (IHostedService)
- **Use Case:** Ticket enrichment worker (JiraTriage.Worker)
- **Key Features:**
  - Lifecycle management (StartAsync/StopAsync)
  - Queue-based processing
  - Graceful shutdown handling

### 2.2 Python Components

#### FastAPI
- **Version:** 0.115.0
- **Use Case:** AI agent HTTP endpoint (ReasoningPlane API)
- **Key Features:**
  - Async request handling (ASGI)
  - Automatic OpenAPI/Swagger documentation
  - Pydantic integration for validation
  - High throughput (comparable to Node.js/Go)

**Sample Endpoint:**
```python
@app.post("/agent/process")
async def process_ticket(request: TicketRequest) -> TicketResponse:
    result = await langgraph_workflow.invoke(request)
    return result
```

#### Uvicorn
- **Version:** 0.32.0
- **Purpose:** ASGI server for FastAPI
- **Configuration:** 
  - Host: 0.0.0.0
  - Port: 8001
  - Workers: 4 (production)
  - Reload: True (development)

---

## 3. AI/ML Framework Stack

### 3.1 LangChain Ecosystem

| Library | Version | Purpose |
|---------|---------|---------|
| langchain | 0.3.7+ | Core LLM orchestration framework |
| langchain-openai | 0.2.9+ | Azure OpenAI integration |
| langchain-community | 0.3.7+ | Third-party connectors |
| langgraph | 0.2.45+ | Multi-agent workflow orchestration |

**Architecture:**
```
LangGraph (Stateful Agent Graphs)
    ↓
LangChain (LLM Abstraction Layer)
    ↓
Azure OpenAI (GPT-4, text-embedding-3-small)
```

### 3.2 Azure OpenAI Integration

**Models Used:**
- **GPT-4 Turbo (1106-preview):** Ticket classification and triage reasoning
- **text-embedding-3-small:** Semantic search embeddings (1536 dimensions)

**Authentication Methods:**
1. **API Key (Development):** Direct key-based auth
2. **Managed Identity (Production):** Azure AD token-based auth

**Configuration:**
```python
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version="2024-05-01-preview",
    deployment_name="gpt-4-turbo",
    temperature=0.3
)

embeddings = AzureOpenAIEmbeddings(
    model="text-embedding-3-small",
    dimensions=1536
)
```

### 3.3 Data Governance & Privacy

#### Presidio (Microsoft)
- **Components:**
  - `presidio-analyzer` (0.2.2): PII detection engine
  - `presidio-anonymizer` (0.2.2): Redaction/masking engine
- **Entities Detected:**
  - EMAIL_ADDRESS
  - PHONE_NUMBER
  - CREDIT_CARD
  - US_SSN
  - IP_ADDRESS
  - PERSON (names via spaCy NER)

**Sample Usage:**
```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
results = analyzer.analyze(text="Contact john@acme.com")
anonymized = AnonymizerEngine().anonymize(text, results)
# Output: "Contact <EMAIL_ADDRESS>"
```

#### spaCy NLP
- **Version:** 3.8+
- **Model:** en_core_web_lg (Large English model)
- **Use Case:** Named Entity Recognition for PII detection

---

## 4. Azure Cloud Services

### 4.1 Data & Storage

| Service | Purpose | Configuration |
|---------|---------|---------------|
| **Azure Cosmos DB** | Immutable decision log storage | NoSQL (JSON documents) |
| | Partition Key: `/ticketId` | |
| | Retention: 7 years | |
| | Consistency: Session | |
| **Azure AI Search** | Vector database for RAG | Semantic Ranker enabled |
| | Index: `ticket-knowledge-base` | |
| | Vector Dimensions: 1536 | |
| | Hybrid Search: Keyword + Vector | |

**Cosmos DB Python Client:**
```python
from azure.cosmos import CosmosClient
client = CosmosClient.from_connection_string(conn_str)
database = client.get_database_client("JiraTriageDB")
container = database.get_container_client("DecisionLogs")
```

**AI Search Python Client:**
```python
from azure.search.documents import SearchClient
client = SearchClient(endpoint, index_name, credential)
results = client.search(
    search_text="database timeout",
    vector_queries=[VectorQuery(vector=embedding, k=5)]
)
```

### 4.2 Messaging & Integration

| Service | Purpose | SDK |
|---------|---------|-----|
| **Azure Service Bus** | Async messaging between .NET ↔ Python | azure-servicebus (Python), Azure.Messaging.ServiceBus (.NET) |
| | Queues: `sanitized-tickets`, `enriched-tickets` | |
| | Max Message Size: 256 KB | |
| | Dead Letter Queue: Enabled | |

**Service Bus Python Publisher:**
```python
from azure.servicebus import ServiceBusClient, ServiceBusMessage
client = ServiceBusClient.from_connection_string(conn_str)
sender = client.get_queue_sender("sanitized-tickets")
await sender.send_messages(ServiceBusMessage(json.dumps(ticket)))
```

### 4.3 Security & Observability

| Service | Purpose | Integration |
|---------|---------|-------------|
| **Azure Key Vault** | Secret management (API keys, connection strings) | azure-keyvault-secrets |
| **Application Insights** | Distributed tracing, metrics, logs | opencensus-ext-azure |
| **Azure AD (Entra ID)** | Authentication, RBAC | azure-identity (DefaultAzureCredential) |

**Key Vault Usage:**
```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://jira-triage-kv.vault.azure.net", credential=credential)
openai_key = client.get_secret("AzureOpenAIKey").value
```

**Application Insights Tracing:**
```python
from opencensus.ext.azure.log_exporter import AzureLogHandler
logger.addHandler(AzureLogHandler(connection_string=insights_conn_str))
```

---

## 5. Data Serialization & Validation

### 5.1 .NET (System.Text.Json)

**Features:**
- High-performance JSON serialization
- Source generators for AOT compilation
- Custom converters for domain models

**Configuration:**
```csharp
JsonSerializerOptions options = new()
{
    PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    WriteIndented = false
};
```

### 5.2 Python (Pydantic)

**Version:** 2.10.0

**Features:**
- Runtime type validation
- Automatic serialization/deserialization
- Custom validators for business rules

**Sample Model:**
```python
from pydantic import BaseModel, Field, EmailStr

class TicketRequest(BaseModel):
    ticket_id: str = Field(..., min_length=1)
    summary: str
    description: str
    reporter_email: EmailStr
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
```

---

## 6. Development & Testing Tools

### 6.1 Testing Frameworks

| Framework | Purpose | Language |
|-----------|---------|----------|
| **pytest** | Unit and integration tests | Python |
| **xUnit** | Unit tests for .NET services | C# |
| **Moq** | Mocking framework (.NET) | C# |

**Sample pytest Test:**
```python
@pytest.mark.asyncio
async def test_ticket_classification():
    request = TicketRequest(ticket_id="T-001", summary="DB timeout")
    response = await agent.classify(request)
    assert response.department == "IT-DBA"
    assert response.confidence > 0.7
```

### 6.2 HTTP Clients

| Library | Purpose | Language |
|---------|---------|----------|
| **httpx** | Async HTTP client for Python | Python |
| **HttpClient** | .NET HTTP client (for JIRA API) | C# |

**Python HTTPX:**
```python
async with httpx.AsyncClient() as client:
    response = await client.post("http://localhost:8001/agent/process", json=data)
```

### 6.3 Environment Management

| Tool | Purpose |
|------|---------|
| **python-dotenv** | Load .env files in Python |
| **Microsoft.Extensions.Configuration** | .NET configuration management |

---

## 7. External API Integrations

### 7.1 JIRA REST API

**Version:** Cloud REST API v3  
**Authentication:** OAuth 2.0 (3-legged) or API Token  
**Operations:**
- Fetch issue details (GET /rest/api/3/issue/{issueKey})
- Update issue fields (PUT /rest/api/3/issue/{issueKey})
- Add comments (POST /rest/api/3/issue/{issueKey}/comment)

### 7.2 Knowledge Base Connectors

| Connector | API | Purpose |
|-----------|-----|---------|
| **Confluence** | REST API v2 | Fetch KB articles for RAG |
| **SharePoint** | Microsoft Graph API | Access company documentation |

**Confluence Connector:**
```python
class ConfluenceConnector:
    def search(self, query: str) -> List[Document]:
        response = requests.get(
            f"{base_url}/rest/api/content/search",
            params={"cql": f"text ~ '{query}'"},
            auth=(user, token)
        )
        return [self._to_document(item) for item in response.json()["results"]]
```

---

## 8. Infrastructure & Deployment

### 8.1 Development Environment

| Component | Technology |
|-----------|-----------|
| **Operating System** | NixOS (Replit) |
| **Package Management** | Nix packages |
| **Process Management** | Replit Workflows |
| **Port Allocation** | 5000 (UI), 5001 (Webhook), 8001 (Python) |

### 8.2 Production Environment (Planned)

| Component | Azure Service |
|-----------|---------------|
| **Control Plane Hosting** | Azure App Service (Linux, .NET 8) |
| **Reasoning Plane Hosting** | Azure Container Instances (Python) |
| **Load Balancer** | Azure Front Door |
| **CDN** | Azure CDN (static assets) |
| **Monitoring** | Azure Monitor + Application Insights |

---

## 9. Security Technologies

### 9.1 Authentication & Authorization

| Technology | Purpose |
|-----------|---------|
| **Azure AD (Entra ID)** | SSO for UI dashboard |
| **JWT Tokens** | Webhook signature validation |
| **RBAC** | Role-based access control |

### 9.2 Encryption

| Type | Technology |
|------|-----------|
| **In Transit** | TLS 1.3 (HTTPS) |
| **At Rest** | Azure Storage Service Encryption (SSE) |
| **Key Management** | Azure Key Vault (HSM-backed) |

---

## 10. Logging & Observability

### 10.1 Structured Logging

| Component | Library | Format |
|-----------|---------|--------|
| **.NET Logging** | Microsoft.Extensions.Logging | JSON (Application Insights) |
| **Python Logging** | Python logging + OpenCensus | JSON (Azure Monitor) |

**Sample .NET Log:**
```csharp
logger.LogInformation(
    "Ticket {TicketId} classified as {Department} with confidence {Confidence}",
    ticketId, department, confidence
);
```

**Sample Python Log:**
```python
logger.info("Ticket processed", extra={
    "ticket_id": ticket_id,
    "department": department,
    "latency_ms": latency
})
```

### 10.2 Distributed Tracing

**Technology:** OpenTelemetry + Azure Application Insights

**Trace Propagation:**
1. .NET Webhook → Service Bus (traceparent header)
2. Python Agent → Azure OpenAI (correlation ID)
3. .NET Worker → Cosmos DB (transaction ID)

---

## 11. Version Control & CI/CD

### 11.1 Version Control

| Tool | Purpose |
|------|---------|
| **Git** | Source control |
| **GitHub** | Repository hosting |
| **.gitignore** | Exclude build artifacts, secrets |

### 11.2 CI/CD (Future)

| Tool | Purpose |
|------|---------|
| **GitHub Actions** | Automated builds and tests |
| **Azure Pipelines** | Deployment to Azure |
| **Docker** | Containerization (Python service) |
| **Terraform/Bicep** | Infrastructure as Code |

---

## 12. Front-End Technologies

### 12.1 UI Framework

| Technology | Version | Purpose |
|-----------|---------|---------|
| **Bootstrap** | 5.3 | Responsive CSS framework |
| **jQuery** | 3.7.1 | DOM manipulation, AJAX |
| **jQuery Validation** | 1.19.5 | Form validation |

### 12.2 Static Assets

- **CSS:** Custom stylesheets + Bootstrap overrides
- **JavaScript:** Minimal client-side logic (form handling)
- **Favicon:** Custom JIRA Triage icon

---

## 13. Development Dependencies

### 13.1 Python Development

```txt
pytest==8.3.3
httpx==0.28.1
python-dotenv==1.0.1
black==24.10.0 (code formatter)
ruff==0.7.0 (linter)
mypy==1.13.0 (type checker)
```

### 13.2 .NET Development

- **EF Core Tools** (future): Database migrations
- **Swashbuckle** (future): OpenAPI documentation
- **BenchmarkDotNet** (future): Performance testing

---

## 14. Technology Selection Rationale

### Why .NET for Control Plane?

1. **Enterprise Integration:** Native Azure SDK support, JIRA REST client
2. **Security:** Built-in CSRF protection, secure secret management
3. **Performance:** Compiled language, efficient JSON serialization
4. **Type Safety:** Strong typing prevents runtime errors in policy enforcement
5. **Ecosystem:** Mature libraries for webhook handling, background services

### Why Python for Reasoning Plane?

1. **AI/ML Ecosystem:** LangChain, LangGraph, Presidio only available in Python
2. **Rapid Iteration:** Quick experimentation with agent prompts and workflows
3. **Community Support:** Extensive Azure OpenAI examples and tutorials
4. **Library Availability:** Native support for all Azure AI services

### Why Hybrid Architecture?

1. **Best of Both Worlds:** Enterprise security (.NET) + AI agility (Python)
2. **Clean Boundaries:** Clear separation of concerns (data governance vs. reasoning)
3. **Team Specialization:** .NET engineers handle infrastructure, data scientists handle agents
4. **Risk Isolation:** LLM failures don't crash control plane

---

## 15. Technology Upgrade Path

### Planned Upgrades (2026)

| Technology | Current | Target | Reason |
|-----------|---------|--------|--------|
| .NET | 8.0 | 9.0 | Performance improvements, native AOT |
| Python | 3.11 | 3.13 | Better async performance |
| LangChain | 0.3.x | 1.0 | Stable API contract |
| Azure OpenAI | GPT-4 | GPT-5 | Enhanced reasoning capabilities |

---

## 16. Technology Constraints

### Current Limitations

1. **No Docker Support:** Replit NixOS environment doesn't support nested virtualization
2. **Single-Region Deployment:** No multi-region Azure setup (future enhancement)
3. **Synchronous Processing:** No parallel ticket processing (queue-based sequential)
4. **In-Memory Queues:** Development only (production uses Azure Service Bus)

---

## Appendix A: Complete Dependency List

### Python (requirements.txt)
```txt
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.10.0
httpx==0.28.1
python-dotenv==1.0.1
langchain==0.3.7
langchain-openai==0.2.9
langchain-community==0.3.7
langgraph==0.2.45
openai==1.54.3
azure-cosmos==4.7.0
azure-search-documents==11.6.0
azure-servicebus==7.12.3
azure-keyvault-secrets==4.9.0
azure-identity==1.19.0
presidio-analyzer==2.2.355
presidio-anonymizer==2.2.355
spacy==3.8.2
opencensus-ext-azure==1.1.13
pytest==8.3.3
```

### .NET (packages via NuGet)
```xml
<PackageReference Include="Azure.Messaging.ServiceBus" Version="7.18.1" />
<PackageReference Include="Azure.Identity" Version="1.13.0" />
<PackageReference Include="Azure.Security.KeyVault.Secrets" Version="4.6.0" />
<PackageReference Include="Microsoft.ApplicationInsights.AspNetCore" Version="2.22.0" />
<PackageReference Include="System.Text.Json" Version="8.0.5" />
```

---

## Appendix B: License Information

All technologies used comply with enterprise licensing requirements:

- **.NET:** MIT License (free for commercial use)
- **Python:** PSF License (permissive)
- **LangChain/LangGraph:** MIT License
- **Azure Services:** Pay-as-you-go (commercial license included)
- **Bootstrap:** MIT License
- **Presidio:** MIT License

---

**Document Control:**
- **Classification:** Internal Technical Documentation
- **Distribution:** Engineering Team, Architecture Review Board
- **Next Review:** Q2 2026
