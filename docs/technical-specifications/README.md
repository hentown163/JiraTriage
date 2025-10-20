# Technical Specifications - JIRA Triage Agent Platform

**Project Status:** ✅ Phase 1 Complete (Production-Ready with Azure Integration)  
**Last Updated:** October 20, 2025

---

## Document Overview

This directory contains comprehensive technical documentation for the JIRA Triage Agent Platform. All documents reflect the **current implemented state** with clear distinctions for future enhancements.

### 📋 Available Documents

| Document | Description | Audience |
|----------|-------------|----------|
| **[01-tech-stack.md](01-tech-stack.md)** | Complete technology breakdown (.NET 8, Python 3.11, Azure services, LangChain/LangGraph) | Engineering, Architecture |
| **[02-project-scope.md](02-project-scope.md)** | End-to-end scope, requirements, acceptance criteria, data flow | Product, Engineering, Stakeholders |
| **[03-high-level-design.md](03-high-level-design.md)** | System architecture, component diagrams, integration points | Engineering, Architecture |
| **[04-low-level-design.md](04-low-level-design.md)** | Implementation details, code structure, API specifications | Engineering Team |
| **[05-database-design.md](05-database-design.md)** | Cosmos DB, Azure AI Search, Service Bus schemas | Engineering, DBAs |
| **[06-future-enhancements-and-limitations.md](06-future-enhancements-and-limitations.md)** | Current limitations and roadmap (Phases 2-4) | Product, Leadership, Engineering |
| **[07-use-cases.md](07-use-cases.md)** | 4 real-world scenarios with ROI calculations | Sales, Product, Executives |

---

## Current Implementation Status

### ✅ Implemented (Phase 1 Complete)

**Control Plane (.NET 8):**
- ✅ JiraTriage.Webhook: HTTP endpoint for JIRA webhooks with DLP redaction
- ✅ JiraTriage.Worker: Background service processing enriched tickets
- ✅ JiraTriage.UI: Razor Pages dashboard for human review
- ✅ JiraTriage.Core: Shared models and services (DlpRedactor, PolicyChecker)

**Reasoning Plane (Python 3.11):**
- ✅ FastAPI service with `/process_ticket` endpoint
- ✅ LangGraph multi-agent workflow (ClassifyNode, RetrieveNode, GenerateNode, PolicyNode)
- ✅ Azure OpenAI integration (GPT-4/GPT-5, text-embedding-3-small)
- ✅ Azure AI Search for hybrid vector+keyword search (RAG)
- ✅ Azure Cosmos DB for immutable decision logging
- ✅ Confluence & SharePoint connectors for knowledge retrieval
- ✅ Enhanced policy engine with vertical slicing (IT, HR, Finance, Legal)
- ✅ Application Insights observability

**Data Governance:**
- ✅ PII redaction (emails, phones, SSNs, credit cards)
- ✅ External email detection
- ✅ Zero-trust architecture (raw data never sent to Python/LLM)

**Deployment:**
- ✅ Development environment (Replit NixOS, in-memory queues)
- ✅ Azure integration ready (Service Bus, Cosmos DB, AI Search, Key Vault)

### ⏳ Future Enhancements (Phases 2-4)

See [06-future-enhancements-and-limitations.md](06-future-enhancements-and-limitations.md) for complete roadmap:
- Phase 2 (Q1-Q2 2026): Active learning, multi-language support, auto-resolution
- Phase 3 (Q3-Q4 2026): Slack/Teams integration, attachment processing (OCR)
- Phase 4 (2027): Multi-tenant support, custom workflow engine, edge deployment

---

## How to Use These Documents

### For Engineering Teams
1. Start with **03-high-level-design.md** for architecture overview
2. Reference **04-low-level-design.md** for implementation details
3. Use **05-database-design.md** for data models and queries
4. Check **01-tech-stack.md** for technology decisions

### For Product/Business Teams
1. Read **07-use-cases.md** for real-world scenarios and ROI
2. Review **02-project-scope.md** for functional requirements
3. Check **06-future-enhancements-and-limitations.md** for roadmap

### For Sales/Marketing
1. Use **07-use-cases.md** for customer conversations
2. Reference **02-project-scope.md** for feature explanations
3. Highlight current implementation status (Phase 1 complete)

### For Executives
1. Start with **07-use-cases.md** (ROI: 1,400%-3,800%)
2. Review **06-future-enhancements-and-limitations.md** for strategic roadmap
3. Reference **02-project-scope.md** for scope and success metrics

---

## Important Notes

### Current vs. Future State

**All documents clearly distinguish:**
- ✅ **Implemented:** Features available in current codebase
- ⏳ **Planned:** Features in future phases (marked with phase numbers)
- ❌ **Out-of-Scope:** Explicitly excluded capabilities

**Example:**
- ✅ LangGraph multi-agent classification: **Implemented**
- ⏳ Multi-language support (Spanish, French, etc.): **Phase 2 (Q1 2026)**
- ❌ Auto-ticket closure: **Out of Phase 1 scope**

### Development vs. Production

**Development Environment (Current):**
- In-memory queues (data lost on restart)
- Single instance deployment
- Environment variables for configuration

**Production Environment (Azure-Ready):**
- Azure Service Bus for durable messaging
- Azure Cosmos DB for persistent decision logs
- Multi-instance deployment with autoscaling
- Azure Key Vault for secret management

**Deployment Path:** Code is Azure-ready; transition requires configuration only (no code changes).

---

## Document Maintenance

### Review Schedule
- **Quarterly:** All documents reviewed for accuracy
- **On Major Changes:** Update relevant documents immediately
- **Before Releases:** Full documentation audit

### Version Control
- All documents versioned with date stamps
- Changes tracked via Git
- Architecture Decision Records (ADRs) in `docs/adr/`

### Contact
- **Engineering Questions:** [Engineering Lead]
- **Product Questions:** [Product Owner]
- **Sales Questions:** [Sales Engineering]

---

## Related Documentation

- `../adr/001-hybrid-polyglot.md` - Architecture Decision Record
- `../../replit.md` - Project README and quick-start guide
- `../../README.md` - Repository README (if applicable)

---

**Last Review:** October 20, 2025  
**Next Review:** January 20, 2026  
**Document Owner:** Technical Architecture Team
