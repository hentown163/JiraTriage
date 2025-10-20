# JIRA Triage Agent Platform

## Overview

An enterprise-grade GenAI-powered autonomous agent platform for intelligent JIRA ticket triage with human-in-the-loop review capabilities. The system implements a **Hybrid Polyglot Architecture with Clean Boundaries and Vertical Slicing**, combining .NET 8 (control plane) and Python 3.11 (reasoning plane) to enforce zero-trust data governance while maintaining AI agility.

**Last Updated:** October 20, 2025  
**Architecture:** Hybrid Polyglot with Vertical Slices and Clean Boundaries  
**Status:** Development (Enterprise Features In Progress)

---

## Project Architecture

### Core Architectural Principles

1. **Polyglot by Necessity**: .NET handles enterprise integration and security; Python manages AI reasoning
2. **Zero-Trust Data Governance**: Sensitive data never leaves .NET boundary
3. **Vertical Slicing**: Each business capability owns its data pipeline, RAG config, and agent graph
4. **Clean Boundaries**: No cross-runtime code sharing; communication via schema-validated async messaging
5. **Immutable Audit Trail**: Full decision provenance for compliance and debugging

### System Components

#### Control Plane (.NET 8)
- **JiraTriage.Core**: Shared models, DLP redaction, policy enforcement
- **JiraTriage.Webhook**: Minimal API for JIRA webhook ingestion (port 5001)
- **JiraTriage.Worker**: Background service for ticket enrichment processing
- **JiraTriage.UI**: Razor Pages dashboard for human review (port 5000)

#### Reasoning Plane (Python 3.11+)
- **FastAPI Service**: Stateless ticket processing endpoint (port 8001)
- **Agent Nodes**: Classification, retrieval, generation, policy validation
- **Vertical Slices**: IT Support, HR Onboarding (extensible)

#### Communication Layer
- **In-Memory Queues**: Development environment (production uses Azure Service Bus)
- **Schema Validation**: Ensures contract compliance across runtimes

---

## Key Features

### Current Implementation (MVP)

✅ **Webhook Ingestion**: Receives JIRA issue_created events  
✅ **DLP Redaction**: Automatically redacts PII (emails, phones, SSN, credit cards)  
✅ **AI Classification**: Department, team, priority prediction with confidence scores  
✅ **Policy Enforcement**: Flags tickets requiring human review  
✅ **Human Review UI**: Razor Pages dashboard for oversight  
✅ **Decision Logging**: Immutable audit trail of all AI decisions  
✅ **Multi-Department Support**: IT Support, HR Onboarding verticals  

### Security & Compliance

- **Zero Data Egress**: Raw JIRA data never sent to Python agent
- **Redaction Flags**: Tracks all sensitive data removal
- **External Email Detection**: Auto-flags tickets from non-internal domains
- **Policy Validation**: Confidence threshold enforcement (0.7 default)
- **Audit Trail**: Full decision provenance with timestamps

---

## Data Flow

```
JIRA Webhook 
  ↓
.NET Webhook API (validate, fetch, redact)
  ↓
In-Memory Queue (sanitized-ticket)
  ↓
Python Agent (classify, retrieve, generate)
  ↓
In-Memory Queue (enriched-ticket)
  ↓
.NET Worker (policy check, update JIRA or flag for review)
  ↓
Razor UI (human review if needed)
```

---

## Usage

### Running Locally

1. **UI Dashboard** (Port 5000): Automatically starts via workflow
   ```
   cd src/ControlPlane/JiraTriage.UI && dotnet run --urls http://0.0.0.0:5000
   ```

2. **Webhook API** (Port 5001):
   ```
   cd src/ControlPlane/JiraTriage.Webhook && dotnet run --urls http://0.0.0.0:5001
   ```

3. **Python Agent** (Port 8001):
   ```
   cd src/ReasoningPlane && python api/main.py
   ```

4. **Worker Service**:
   ```
   cd src/ControlPlane/JiraTriage.Worker && dotnet run
   ```

### Testing Webhook

```bash
curl -X POST http://localhost:5001/api/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "webhookEvent": "jira:issue_created",
    "timestamp": 1697000000,
    "issue": {
      "id": "10001",
      "key": "PROJ-123",
      "fields": {
        "summary": "Database connection timeout",
        "description": "Can not connect to staging DB - timeout after 30s",
        "issueType": { "name": "Bug" },
        "priority": { "name": "High" },
        "reporter": {
          "accountId": "user123",
          "displayName": "John Doe",
          "emailAddress": "john@company.com"
        }
      }
    }
  }'
```

---

## Future Enhancements

### Phase 1: Production Readiness (Q1 2026)

#### Infrastructure
- [ ] **Azure Service Bus Integration**: Replace in-memory queues with durable messaging
- [ ] **Azure Cosmos DB**: Immutable decision log storage with 7-year retention
- [ ] **Azure AI Search**: Vector index for RAG knowledge base
- [ ] **Azure Key Vault**: Centralized secret management
- [ ] **Application Insights**: Distributed tracing and observability
- [ ] **Managed Identity**: Eliminate stored credentials

#### Scalability
- [ ] **Horizontal Scaling**: Multiple worker instances
- [ ] **Rate Limiting**: Per-department quotas for API calls
- [ ] **Circuit Breakers**: Fault isolation for external connectors
- [ ] **Autoscaling**: Based on queue depth and latency

#### Authentication & Authorization
- [ ] **Azure AD Integration**: SSO for Razor UI
- [ ] **RBAC**: Role-based access (Reviewer, Admin, Auditor)
- [ ] **API Key Management**: Webhook signature validation
- [ ] **Audit Logging**: User action tracking in UI

### Phase 2: AI Enhancement (Q2 2026)

#### LangGraph Integration
- [ ] **Multi-Agent Graphs**: Separate graphs per vertical slice
- [ ] **Memory Layer**: Conversation history for complex tickets
- [ ] **Tool Calling**: Dynamic connector selection
- [ ] **Human-in-the-Loop Nodes**: Approval gates in workflow

#### RAG Improvements
- [ ] **Hybrid Search**: Keyword + vector retrieval
- [ ] **Reranking**: Cross-encoder for citation relevance
- [ ] **Dynamic Connectors**: 
  - SharePoint Graph API
  - Confluence Cloud REST API
  - Salesforce CRM
  - ServiceNow CMDB
- [ ] **Permission-Aware Retrieval**: Post-filtering based on user ACLs
- [ ] **Chunk Optimization**: Semantic splitting with overlap

#### Model Improvements
- [ ] **Fine-Tuning**: Department-specific classification models
- [ ] **Ensemble Predictions**: Majority voting across models
- [ ] **Confidence Calibration**: Temperature scaling
- [ ] **A/B Testing**: Per-vertical model experiments
- [ ] **Feedback Loop**: Learn from human overrides

### Phase 3: Advanced Features (Q3 2026)

#### Multi-Source Triage
- [ ] **Email Integration**: Direct email-to-ticket creation
- [ ] **Slack Bot**: Interactive triage in Slack channels
- [ ] **Teams Integration**: Adaptive cards for approvals
- [ ] **ServiceNow Sync**: Bi-directional incident sync

#### Automation
- [ ] **Auto-Resolution**: Close tickets with known solutions
- [ ] **SLA Monitoring**: Predict and prevent SLA breaches
- [ ] **Smart Routing**: Load balancing across team members
- [ ] **Escalation Logic**: Auto-escalate stale tickets

#### Analytics & Reporting
- [ ] **Power BI Dashboards**: Executive metrics
- [ ] **Override Analysis**: Why humans disagree with AI
- [ ] **Department Scorecards**: Precision, recall, latency
- [ ] **Cost Attribution**: LLM API usage per department

### Phase 4: Enterprise Scale (Q4 2026)

#### Multi-Tenant Support
- [ ] **Organization Isolation**: Separate vector indexes
- [ ] **Custom Verticals**: Per-customer domain slices
- [ ] **White Labeling**: Branded UI themes

#### Advanced Compliance
- [ ] **GDPR Right to Erasure**: Automated data deletion
- [ ] **SOC 2 Type II**: Audit-ready logging
- [ ] **HIPAA Compliance**: PHI handling for healthcare
- [ ] **Data Residency**: Region-specific deployments

#### Performance Optimization
- [ ] **Edge Caching**: Frequently retrieved KB articles
- [ ] **Batch Processing**: Group similar tickets
- [ ] **Streaming Responses**: Progressive UI updates
- [ ] **Preemptive Classification**: Process before full webhook

---

## Current Limitations

### Technical Limitations

1. **Local Development Only**
   - In-memory queues (data lost on restart)
   - No persistent decision log storage
   - Single-instance only (no scaling)

2. **Mock AI Components**
   - Simplified classification logic (keyword matching)
   - No real LLM integration (placeholder responses)
   - No vector database (ChromaDB/Azure AI Search not configured)
   - No LangGraph implementation (basic FastAPI endpoints)

3. **Missing Connectors**
   - No SharePoint integration
   - No Confluence integration
   - No CRM connectors
   - No actual JIRA API client (mock only)

4. **Security Gaps**
   - No webhook signature validation
   - No HTTPS/TLS in development
   - Secrets in environment variables (not Key Vault)
   - No rate limiting or throttling

5. **Observability**
   - Console logging only (no structured logging)
   - No distributed tracing
   - No metrics collection
   - No alerting

### Functional Limitations

1. **Incomplete UI**
   - Review workflow not fully implemented
   - No ticket detail view
   - No approval/override actions
   - Static dashboard metrics

2. **No Historical Data**
   - Decision logs not persisted
   - No analytics or reporting
   - No trend analysis
   - No model performance tracking

3. **Single Language**
   - English-only classification
   - No multi-language support

4. **Limited Vertical Slices**
   - Only IT Support and HR Onboarding mocks
   - No Finance, Legal, or custom verticals

5. **No Feedback Loop**
   - Human overrides not used for retraining
   - No active learning
   - No model improvement pipeline

### Scalability Limitations

1. **In-Memory State**
   - Queue data volatile
   - No message replay capability
   - No dead letter queue

2. **Single Runtime**
   - Python agent must be manually started
   - No containerization
   - No orchestration (Kubernetes)

3. **Synchronous Processing**
   - Worker processes tickets sequentially
   - No parallel ticket processing
   - No priority queue

### Compliance Limitations

1. **Data Retention**
   - No automatic log archival
   - No GDPR deletion workflow
   - No encryption at rest

2. **Audit Trail**
   - Decision logs in memory only
   - No tamper-proof storage
   - No compliance reporting

3. **Access Control**
   - No authentication in UI
   - No authorization checks
   - No audit of user actions

---

## Why These Limitations Exist

This is an **MVP/Proof-of-Concept** implementation demonstrating:
- Hybrid polyglot architecture feasibility
- .NET ↔ Python integration patterns
- Zero-trust data flow design
- Human-in-the-loop UX patterns

**Not Production-Ready**: This system requires the Phase 1 enhancements (Azure services, authentication, persistence) before enterprise deployment.

---

## Migration Path to Production

### Step 1: Infrastructure (2-3 weeks)
1. Deploy to Azure App Service (.NET) + Azure Container Instances (Python)
2. Configure Azure Service Bus for messaging
3. Set up Azure Cosmos DB for decision logs
4. Integrate Azure Key Vault for secrets
5. Enable Application Insights

### Step 2: Security (1-2 weeks)
1. Implement Azure AD authentication
2. Add webhook signature validation
3. Enable HTTPS/TLS everywhere
4. Configure RBAC policies

### Step 3: AI Integration (3-4 weeks)
1. Integrate Azure OpenAI (GPT-4)
2. Set up Azure AI Search with vector indexes
3. Implement LangGraph multi-agent workflows
4. Connect SharePoint/Confluence

### Step 4: Testing & Validation (2-3 weeks)
1. End-to-end integration tests
2. Load testing (1000 tickets/hour)
3. Security penetration testing
4. Compliance audit preparation

**Total Estimated Effort**: 8-12 weeks with 2-3 engineers

---

## Technologies Used

### Control Plane
- .NET 8.0
- ASP.NET Core Minimal API
- ASP.NET Core Razor Pages
- System.Text.Json
- Background Services (IHostedService)

### Reasoning Plane
- Python 3.11
- FastAPI
- Pydantic
- Uvicorn
- (Future: LangChain, LangGraph, ChromaDB)

### Development Environment
- Replit (NixOS)
- In-memory queues (development)
- Console logging

---

## Contributing

This is an architectural reference implementation. For production use:

1. Review the "Future Enhancements" roadmap
2. Implement Phase 1 infrastructure requirements
3. Follow the migration path to Azure
4. Adapt vertical slices to your specific departments
5. Integrate with your actual JIRA instance

---

## License

This is an educational/reference architecture. Adapt for your enterprise needs.

---

## Architecture Decision Records

See `docs/adr/001-hybrid-polyglot.md` for the full architectural justification.

---

## Support & Contact

For questions about this architecture pattern:
- Review the attached specification documents
- Consult Microsoft Azure AI architecture patterns
- Reference LangGraph documentation for agent workflows

**Built with**: Enterprise Cloud AI Architecture principles (PhD-level design)
