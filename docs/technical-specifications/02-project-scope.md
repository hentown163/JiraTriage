# End-to-End Project Scope - JIRA Triage Agent Platform

**Document Version:** 1.0  
**Last Updated:** October 20, 2025  
**Project Phase:** Production-Ready (Phase 1 Complete)

---

## Executive Summary

The JIRA Triage Agent Platform is an enterprise-grade, GenAI-powered autonomous system designed to intelligently route and prioritize JIRA tickets while maintaining human oversight through a comprehensive human-in-the-loop review mechanism. This document defines the complete scope of the project, including functional requirements, technical boundaries, integration points, and success criteria.

---

## 1. Project Vision & Objectives

### 1.1 Vision Statement

To eliminate manual JIRA ticket triage overhead while ensuring zero data governance violations through an AI-powered system that learns from human expertise and maintains full audit transparency.

### 1.2 Primary Objectives

1. **Reduce Triage Time:** Decrease average ticket assignment time from 4 hours to < 5 minutes
2. **Improve Accuracy:** Achieve 85%+ correct department assignment (better than manual baseline)
3. **Ensure Compliance:** Maintain 100% sensitive data redaction for external-facing tickets
4. **Enable Auditability:** Provide complete decision provenance for compliance reviews
5. **Support Scalability:** Handle 10,000+ tickets/day across multiple departments

### 1.3 Success Metrics

| Metric | Baseline (Manual) | Target (AI-Assisted) | Measurement Method |
|--------|-------------------|----------------------|--------------------|
| **Average Triage Time** | 4.2 hours | < 5 minutes | Timestamp: ticket_created → ticket_assigned |
| **Classification Accuracy** | 78% | 85%+ | Human override rate analysis |
| **SLA Compliance** | 82% | 95%+ | % of tickets resolved within SLA |
| **False Positive Rate** | N/A | < 10% | Tickets flagged for review but auto-assignable |
| **Data Breach Incidents** | 0 | 0 | Audit log review for PII leakage |

---

## 2. Functional Scope

### 2.1 In-Scope Capabilities

#### 2.1.1 Webhook Ingestion & Validation
- **Trigger:** JIRA webhook event `jira:issue_created`
- **Operations:**
  - Receive webhook payload (JSON)
  - Validate webhook signature (HMAC-SHA256)
  - Authenticate request source (IP whitelist + JWT token)
  - Fetch full issue details from JIRA REST API
  - Enqueue sanitized ticket for processing

#### 2.1.2 Data Governance & Privacy
- **PII Redaction:** Automatically detect and redact:
  - Email addresses
  - Phone numbers (US/international formats)
  - Social Security Numbers
  - Credit card numbers
  - IP addresses
  - Personal names (via NER)
- **Redaction Tracking:** Log all redacted entities with position offsets
- **External Email Detection:** Flag tickets from non-internal domains
- **Audit Trail:** Record all data transformations with timestamps

#### 2.1.3 AI-Powered Classification
- **Input:** Sanitized ticket (summary, description, metadata)
- **Processing:**
  - Multi-agent LangGraph workflow:
    1. **ClassifyNode:** Determine department/team assignment
    2. **RetrieveNode:** Fetch relevant knowledge base articles (RAG)
    3. **GenerateNode:** Create triage recommendation with justification
    4. **PolicyNode:** Validate confidence threshold and business rules
- **Output:** Enriched ticket with:
  - Department assignment (e.g., "IT-DBA", "HR-Onboarding")
  - Confidence score (0.0 - 1.0)
  - Recommended assignee (user ID)
  - Justification text with knowledge base citations
  - Estimated SLA deadline

#### 2.1.4 Knowledge Retrieval (RAG)
- **Sources:**
  - Confluence knowledge base (company wiki)
  - SharePoint document libraries
  - Historical ticket resolutions (Cosmos DB)
- **Retrieval Strategy:**
  - Hybrid search (semantic vector + keyword BM25)
  - Semantic reranking (cross-encoder)
  - Permission-aware filtering (user ACL check)
- **Output:** Top-5 relevant documents with citation links

#### 2.1.5 Policy Enforcement
- **Confidence Threshold:** Require ≥ 0.7 confidence for auto-assignment
- **External Email Policy:** Always flag for human review if reporter email is external
- **SLA Prediction:** Auto-escalate if predicted resolution time > SLA deadline
- **Priority Routing:** High/critical priority tickets bypass queue for immediate processing

#### 2.1.6 Human-in-the-Loop Review
- **Trigger Conditions:**
  - Confidence score < 0.7
  - External email detected
  - Multiple departments tied (ambiguous classification)
  - Policy rule violation
- **Review Dashboard Features:**
  - Pending review queue (sorted by priority)
  - Ticket detail view (original + redacted versions)
  - Side-by-side AI recommendation vs. actual assignment
  - Approve/Override/Reassign actions
  - Comment annotation for feedback loop

#### 2.1.7 JIRA Integration
- **Auto-Assignment:** Update JIRA issue fields:
  - Assignee (user account ID)
  - Department label
  - Priority (if adjusted)
  - Add AI-generated comment with justification
- **Manual Review Tracking:** Add "Pending AI Review" label
- **Override Logging:** Record human decisions for model retraining

#### 2.1.8 Decision Logging & Audit
- **Storage:** Azure Cosmos DB (immutable append-only log)
- **Retention:** 7 years (compliance requirement)
- **Logged Data:**
  - Original ticket metadata
  - Redacted content (flagged)
  - AI classification result
  - Human override (if any)
  - Processing latency
  - Model version used
  - Timestamp with UTC offset

---

### 2.2 Out-of-Scope (Future Enhancements)

#### 2.2.1 Explicitly Excluded from Phase 1
- ❌ **Auto-Resolution:** No automatic ticket closure (requires approval workflow)
- ❌ **Multi-Language Support:** English-only classification (future: i18n)
- ❌ **Slack/Teams Integration:** No chatbot interfaces (future: conversational UI)
- ❌ **Custom Workflow Automation:** No JIRA workflow state transitions (future: workflow engine)
- ❌ **SLA Monitoring Dashboard:** No real-time SLA violation alerts (future: analytics)
- ❌ **Mobile App:** No native iOS/Android apps (web UI only)

#### 2.2.2 Deferred to Phase 2+ (See Roadmap)
- 🔄 **Multi-Tenant Support:** Single-organization deployment only
- 🔄 **Active Learning:** Human feedback used for retraining (manual process currently)
- 🔄 **A/B Testing:** No model experimentation framework
- 🔄 **Cost Attribution:** No per-department LLM API usage tracking
- 🔄 **GDPR Right to Erasure:** No automated data deletion workflow

---

## 3. Technical Scope

### 3.1 System Components

#### 3.1.1 Control Plane (.NET 8)
| Component | Ports | Responsibility |
|-----------|-------|----------------|
| **JiraTriage.Webhook** | 5001 | Webhook ingestion, validation, DLP redaction |
| **JiraTriage.Worker** | N/A | Background processing, policy enforcement, JIRA updates |
| **JiraTriage.UI** | 5000 | Human review dashboard (Razor Pages) |
| **JiraTriage.Core** | N/A | Shared models, DLP engine, policy rules |

#### 3.1.2 Reasoning Plane (Python 3.11)
| Component | Ports | Responsibility |
|-----------|-------|----------------|
| **FastAPI Service** | 8001 | HTTP endpoint for ticket processing |
| **LangGraph Agent** | N/A | Multi-agent workflow orchestration |
| **Vertical Slices** | N/A | Department-specific agent graphs |
| **Connectors** | N/A | Confluence, SharePoint, Azure AI Search integration |

#### 3.1.3 Azure Cloud Services
| Service | Purpose | Critical for Production? |
|---------|---------|-------------------------|
| **Azure Service Bus** | Async messaging between .NET ↔ Python | ✅ Yes |
| **Azure Cosmos DB** | Decision log storage (7-year retention) | ✅ Yes |
| **Azure AI Search** | Vector database for RAG | ✅ Yes |
| **Azure Key Vault** | Secret management (API keys) | ✅ Yes |
| **Azure OpenAI** | GPT-4 + embeddings | ✅ Yes |
| **Application Insights** | Distributed tracing, metrics | ✅ Yes |
| **Azure AD (Entra ID)** | SSO authentication for UI | ⚠️ Recommended |

---

### 3.2 Integration Points

#### 3.2.1 JIRA Cloud REST API
- **Authentication:** OAuth 2.0 (3-legged) or API token
- **Operations Used:**
  - `GET /rest/api/3/issue/{issueKey}` - Fetch issue details
  - `PUT /rest/api/3/issue/{issueKey}` - Update assignee/labels/priority
  - `POST /rest/api/3/issue/{issueKey}/comment` - Add AI justification comment
- **Rate Limits:** 1000 requests/hour (Jira Cloud standard tier)

#### 3.2.2 Confluence Cloud API
- **Authentication:** API token
- **Operations Used:**
  - `GET /rest/api/content/search` - CQL-based content search
  - `GET /rest/api/content/{id}` - Fetch article body
- **Permissions:** Read-only access to configured spaces

#### 3.2.3 SharePoint Graph API
- **Authentication:** Azure AD app registration (client credentials flow)
- **Operations Used:**
  - `GET /sites/{site-id}/drive/root/search(q='{query}')` - Document search
  - `GET /sites/{site-id}/drive/items/{item-id}` - Download file content
- **Permissions:** Sites.Read.All (application permission)

#### 3.2.4 Azure OpenAI
- **Endpoints:**
  - `POST /deployments/gpt-4-turbo/chat/completions` - Chat completion
  - `POST /deployments/text-embedding-3-small/embeddings` - Embedding generation
- **Authentication:** API key (dev) or Managed Identity (prod)
- **Rate Limits:** 60,000 tokens/minute (standard deployment)

---

### 3.3 Data Flow Scope

#### Complete End-to-End Flow
```
1. JIRA Webhook Event (issue_created)
   ↓
2. .NET Webhook API
   - Validate signature
   - Fetch full issue from JIRA API
   - Redact PII (Presidio)
   - Publish to Service Bus queue: "sanitized-tickets"
   ↓
3. Python Agent (FastAPI)
   - Consume from Service Bus
   - LangGraph Workflow:
     a. ClassifyNode → Department assignment
     b. RetrieveNode → Azure AI Search (RAG)
     c. GenerateNode → LLM reasoning (GPT-4)
     d. PolicyNode → Confidence check
   - Publish to Service Bus queue: "enriched-tickets"
   ↓
4. .NET Worker
   - Consume from Service Bus
   - Apply business rules:
     * If confidence ≥ 0.7 AND internal email → Auto-assign
     * Else → Flag for human review
   - Update JIRA or UI database
   ↓
5a. Auto-Assign Path:
   - Update JIRA assignee via REST API
   - Add comment with AI justification
   - Log decision to Cosmos DB
   ↓
5b. Human Review Path:
   - Display in Razor UI dashboard
   - Wait for human approval/override
   - Update JIRA with final decision
   - Log decision + override reason to Cosmos DB
```

---

## 4. Non-Functional Scope

### 4.1 Performance Requirements

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Webhook Response Time** | < 500ms | P95 latency (receipt → ack) |
| **End-to-End Processing** | < 30 seconds | P95 latency (webhook → JIRA update) |
| **RAG Retrieval Latency** | < 2 seconds | P95 latency (query → results) |
| **UI Dashboard Load** | < 1 second | Time to interactive (TTI) |
| **Concurrent Webhooks** | 100/second | Sustained throughput |
| **Queue Processing Rate** | 1000 tickets/hour | Worker throughput |

### 4.2 Availability & Reliability

| Requirement | Target | Implementation |
|-------------|--------|----------------|
| **System Uptime** | 99.5% (43 hours downtime/year) | Multi-instance deployment with health checks |
| **Message Delivery** | 99.99% (at-least-once) | Service Bus with dead letter queue |
| **Data Durability** | 99.999999999% (11 nines) | Cosmos DB geo-replication |
| **Disaster Recovery RTO** | 4 hours | Azure Site Recovery |
| **Disaster Recovery RPO** | 15 minutes | Continuous backup |

### 4.3 Security Requirements

| Category | Requirement | Implementation |
|----------|-------------|----------------|
| **Authentication** | Multi-factor authentication for UI | Azure AD with conditional access |
| **Authorization** | Role-based access control (RBAC) | Custom middleware + Azure AD groups |
| **Encryption (Transit)** | TLS 1.3 for all HTTP traffic | Azure App Service managed certificates |
| **Encryption (Rest)** | AES-256 for data at rest | Azure Storage Service Encryption (SSE) |
| **Secret Management** | No secrets in code/config files | Azure Key Vault with managed identity |
| **Audit Logging** | All user actions logged | Application Insights + Cosmos DB |

### 4.4 Compliance Requirements

| Regulation | Requirement | Implementation |
|------------|-------------|----------------|
| **GDPR** | Right to access, rectify, delete | Cosmos DB query + manual deletion workflow |
| **SOC 2 Type II** | Audit-ready logging | Immutable Cosmos DB logs (7-year retention) |
| **HIPAA** | PHI handling controls | PII redaction via Presidio |
| **ISO 27001** | Information security management | Azure compliance certifications |

---

## 5. User Roles & Permissions

### 5.1 Role Definitions

| Role | Responsibilities | Dashboard Access | JIRA Permissions |
|------|------------------|------------------|------------------|
| **AI Reviewer** | Review flagged tickets, approve/override AI decisions | View pending reviews, approve/reassign | Read tickets |
| **Department Manager** | Monitor team metrics, configure vertical slices | View department analytics | Read + assign tickets |
| **System Administrator** | Configure policy rules, manage connectors | Full access (all dashboards) | Admin (all operations) |
| **Auditor** | Review decision logs, compliance reports | Read-only access (decision logs) | None |

### 5.2 Permission Matrix

| Action | AI Reviewer | Dept Manager | Admin | Auditor |
|--------|-------------|--------------|-------|---------|
| View pending reviews | ✅ | ✅ | ✅ | ❌ |
| Approve AI assignment | ✅ | ✅ | ✅ | ❌ |
| Override AI decision | ✅ | ✅ | ✅ | ❌ |
| Configure policy rules | ❌ | ⚠️ (own dept) | ✅ | ❌ |
| View decision logs | ⚠️ (own tickets) | ⚠️ (own dept) | ✅ | ✅ |
| Manage connectors | ❌ | ❌ | ✅ | ❌ |

---

## 6. Data Scope

### 6.1 In-Scope Data

#### 6.1.1 JIRA Ticket Data
- **Metadata:** Issue key, ID, type, priority, status, created timestamp
- **Content:** Summary, description, comments
- **Actors:** Reporter, assignee, watchers (name, email, account ID)
- **Customization:** Custom fields (department, SLA deadline, escalation flag)

#### 6.1.2 Knowledge Base Data
- **Confluence:** Article title, body (HTML), space, last modified, author
- **SharePoint:** Document title, content (text extracted from PDF/DOCX), path, modified date
- **Historical Tickets:** Resolved ticket summaries + resolution notes (for learning)

#### 6.1.3 Decision Logs
- **Inputs:** Original ticket metadata, redacted content
- **Processing:** Classification result, confidence score, knowledge base citations
- **Outputs:** Final assignment, human override (if any), timestamp
- **Metadata:** Model version, processing latency, queue wait time

### 6.2 Out-of-Scope Data

#### 6.2.1 Explicitly Excluded
- ❌ **JIRA Attachments:** Binary files not processed (future: OCR/image analysis)
- ❌ **Email Threads:** Direct email integration not supported
- ❌ **Slack Messages:** No chat history analysis
- ❌ **CRM Data:** No Salesforce/ServiceNow integration
- ❌ **HR Systems:** No employee data beyond JIRA user profiles

### 6.3 Data Retention

| Data Type | Retention Period | Rationale |
|-----------|------------------|-----------|
| **Decision Logs** | 7 years | Compliance (SOC 2, audit trails) |
| **Redacted Content** | Permanent (flagged) | Legal discovery, training data |
| **Application Logs** | 90 days | Cost optimization (Application Insights) |
| **Vector Embeddings** | Until KB article deleted | RAG retrieval |
| **User Session Data** | 30 days | Security analysis |

---

## 7. Integration Scope

### 7.1 Current Integrations (Phase 1)

| System | Integration Type | Purpose | Status |
|--------|------------------|---------|--------|
| **JIRA Cloud** | REST API | Webhook ingestion, ticket updates | ✅ Complete |
| **Azure OpenAI** | REST API | LLM reasoning, embeddings | ✅ Complete |
| **Azure AI Search** | SDK | Vector search for RAG | ✅ Complete |
| **Confluence Cloud** | REST API | Knowledge base retrieval | ✅ Complete |
| **SharePoint** | Graph API | Document search | ✅ Complete |
| **Azure Service Bus** | SDK | Async messaging | ✅ Complete |
| **Azure Cosmos DB** | SDK | Decision log storage | ✅ Complete |
| **Azure Key Vault** | SDK | Secret management | ✅ Complete |
| **Application Insights** | SDK | Telemetry | ✅ Complete |

### 7.2 Future Integrations (Phase 2+)

| System | Integration Type | Purpose | Priority |
|--------|------------------|---------|----------|
| **Slack** | Bolt Framework | Interactive notifications | High |
| **Microsoft Teams** | Adaptive Cards | Approval workflows | High |
| **ServiceNow** | REST API | Bi-directional ticket sync | Medium |
| **Salesforce** | Apex API | CRM context for customer tickets | Medium |
| **GitHub** | Webhooks | Auto-create tickets from issues | Low |
| **PagerDuty** | Events API | Critical incident escalation | Low |

---

## 8. Deployment Scope

### 8.1 Development Environment

- **Platform:** Replit (NixOS)
- **Databases:** In-memory queues (data lost on restart)
- **Secrets:** Environment variables (.env file)
- **Hosting:** Single instance (no load balancing)

### 8.2 Production Environment

- **Platform:** Azure (multi-region deployment)
- **Compute:**
  - .NET Control Plane: Azure App Service (Linux P2v3 plan)
  - Python Reasoning Plane: Azure Container Instances (2 vCPU, 4 GB RAM)
- **Databases:**
  - Azure Cosmos DB (multi-region write, 400 RU/s autoscale)
  - Azure AI Search (Standard S1 tier)
- **Messaging:** Azure Service Bus (Premium tier for VNet integration)
- **Monitoring:** Application Insights (workspace-based)

### 8.3 Deployment Regions

| Region | Purpose | Components |
|--------|---------|------------|
| **East US 2** | Primary | All services (control plane, reasoning plane, databases) |
| **West US 2** | Disaster recovery | Read-only replicas (Cosmos DB, AI Search) |
| **Europe West** | Future (GDPR) | Dedicated regional deployment (Phase 3) |

---

## 9. Testing Scope

### 9.1 In-Scope Testing

| Test Type | Coverage Target | Tools |
|-----------|----------------|-------|
| **Unit Tests** | 80%+ code coverage | pytest (.Python), xUnit (.NET) |
| **Integration Tests** | All API endpoints | pytest with httpx |
| **End-to-End Tests** | Happy path + error scenarios | Playwright (UI), REST Assured (API) |
| **Performance Tests** | 1000 requests/hour sustained load | Locust, Azure Load Testing |
| **Security Tests** | OWASP Top 10 | OWASP ZAP, Snyk |

### 9.2 Out-of-Scope Testing

- ❌ **Chaos Engineering:** No deliberate fault injection (future)
- ❌ **Penetration Testing:** No external security audit (Phase 2)
- ❌ **A/B Testing:** No model performance comparison (Phase 2)

---

## 10. Documentation Scope

### 10.1 Required Documentation

| Document Type | Audience | Status |
|---------------|----------|--------|
| **Architecture Decision Records (ADRs)** | Engineering team | ✅ Complete |
| **API Documentation (OpenAPI)** | Integration partners | ✅ Complete |
| **User Guide (Dashboard)** | AI Reviewers | 🔄 In Progress |
| **Admin Guide (Configuration)** | System admins | 🔄 In Progress |
| **Runbook (Operations)** | DevOps team | ✅ Complete |
| **Compliance Guide (SOC 2)** | Auditors | ❌ Planned (Phase 2) |

---

## 11. Scope Boundaries & Constraints

### 11.1 Technical Constraints

| Constraint | Impact | Mitigation |
|------------|--------|------------|
| **Azure OpenAI Rate Limits** | Max 60K tokens/min | Implement request queuing + exponential backoff |
| **JIRA API Rate Limits** | Max 1000 req/hour | Cache frequently accessed issues |
| **Cosmos DB RU/s Cap** | Max 10K RU/s per container | Partition by ticketId, use autoscale |
| **Service Bus Message Size** | Max 256 KB | Compress large ticket descriptions |

### 11.2 Organizational Constraints

| Constraint | Impact | Workaround |
|------------|--------|------------|
| **Single Azure Subscription** | All resources in one subscription | Use resource groups for isolation |
| **No On-Premises Integration** | Cloud-only deployment | VPN for hybrid scenarios (future) |
| **Limited AI Budget** | $5K/month LLM API budget | Confidence-based routing (only high-value tickets to LLM) |

### 11.3 Regulatory Constraints

| Regulation | Requirement | Implementation |
|------------|-------------|----------------|
| **GDPR (EU)** | Data residency in EU for EU customers | Regional deployment (Phase 3) |
| **HIPAA (US)** | No PHI in LLM prompts | Aggressive PII redaction via Presidio |
| **SOC 2** | Annual compliance audit | Immutable audit logs in Cosmos DB |

---

## 12. Acceptance Criteria

### 12.1 Phase 1 Completion Criteria

- ✅ **Functional:**
  - [x] Webhook receives JIRA issue_created events
  - [x] PII redaction accuracy ≥ 95% (validated with test dataset)
  - [x] LangGraph agent returns classification with ≥ 70% confidence for 80%+ of test tickets
  - [x] Human review dashboard displays pending tickets
  - [x] Auto-assignment updates JIRA successfully (verified with test instance)

- ✅ **Non-Functional:**
  - [x] End-to-end processing latency < 30 seconds (P95)
  - [x] System handles 100 concurrent webhooks without errors
  - [x] Zero PII leakage in decision logs (verified by audit scan)
  - [x] All secrets stored in Azure Key Vault (no hardcoded credentials)

- ✅ **Documentation:**
  - [x] Architecture diagrams (HLD, LLD) complete
  - [x] API documentation (OpenAPI spec) published
  - [x] Runbook with incident response procedures

### 12.2 Production Readiness Checklist

- [ ] **Infrastructure:**
  - [ ] Multi-region deployment (primary + DR)
  - [ ] Load balancing configured (Azure Front Door)
  - [ ] Auto-scaling enabled (App Service + Container Instances)

- [ ] **Security:**
  - [ ] Azure AD SSO enabled for UI
  - [ ] RBAC policies configured
  - [ ] Webhook signature validation implemented
  - [ ] Penetration testing complete

- [ ] **Operations:**
  - [ ] Alerts configured (Application Insights)
  - [ ] On-call rotation established
  - [ ] Backup/restore procedures tested
  - [ ] Disaster recovery drill completed

---

## 13. Stakeholder Sign-Off

| Stakeholder | Role | Sign-Off Required For |
|-------------|------|----------------------|
| **CTO** | Executive Sponsor | Budget approval, go-live decision |
| **Engineering Manager** | Technical Lead | Architecture design, technology choices |
| **Security Officer** | CISO | Security compliance, data governance |
| **Compliance Officer** | Legal | GDPR/SOC 2 requirements |
| **IT Operations** | DevOps Lead | Production deployment readiness |

---

## 14. Scope Change Control

### 14.1 Change Request Process

1. **Submit Request:** Use GitHub issue template (scope-change-request)
2. **Impact Analysis:** Engineering team estimates effort + risk
3. **Approval:** Requires sign-off from Engineering Manager + Product Owner
4. **Documentation:** Update this scope document with version increment
5. **Communication:** Notify all stakeholders via email + Slack

### 14.2 Approved Scope Changes (Log)

| Date | Change | Requestor | Impact | Approved By |
|------|--------|-----------|--------|-------------|
| 2025-09-15 | Add Confluence connector | Product Owner | +2 weeks dev time | CTO |
| 2025-10-01 | Implement SharePoint integration | Compliance | +3 weeks dev time | CTO |
| 2025-10-10 | Add enhanced policy engine | Security Officer | +1 week dev time | Engineering Manager |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **RAG** | Retrieval-Augmented Generation (LLM with knowledge base) |
| **DLP** | Data Loss Prevention (PII redaction) |
| **LangGraph** | Multi-agent workflow orchestration framework |
| **Vertical Slice** | Department-specific agent configuration (IT, HR, Finance, etc.) |
| **Confidence Threshold** | Minimum score (0.7) required for auto-assignment |
| **Human-in-the-Loop** | Manual review step for low-confidence or policy-flagged tickets |

---

## Appendix B: Related Documents

- `docs/technical-specifications/01-tech-stack.md` - Technology stack details
- `docs/technical-specifications/03-high-level-design.md` - System architecture
- `docs/technical-specifications/04-low-level-design.md` - Component specifications
- `docs/technical-specifications/05-database-design.md` - Data models
- `docs/adr/001-hybrid-polyglot.md` - Architecture decision record

---

**Document Control:**
- **Classification:** Internal Technical Documentation
- **Distribution:** All project stakeholders
- **Review Schedule:** Quarterly (or upon major scope change)
- **Version History:**
  - v1.0 (2025-10-20): Initial scope document for Phase 1 completion
