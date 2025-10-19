# ADR 001: Hybrid Polyglot Architecture with Clean Boundaries

**Status:** Accepted  
**Date:** 2025-10-19  
**Decision Makers:** Enterprise Cloud AI Architect Team  
**Context:** GenAI-powered JIRA Triage Agent for enterprise environments

---

## Context and Problem Statement

We need to build an autonomous GenAI agent for JIRA ticket triage that satisfies:

1. **Security & Compliance**: PII/IP data must never leave secure zones
2. **AI Agility**: Rapid experimentation with LangGraph, LLMs, RAG strategies
3. **Enterprise Integration**: JIRA, SharePoint, Confluence, CRM with OAuth/RBAC
4. **Observability**: Full audit trail for every AI decision
5. **Scalability**: Handle ticket spikes without cascading failures

Traditional monolithic or microservices approaches fail because:
- **Monolithic**: Cannot isolate security domains or scale AI vs. integration layers independently
- **Microservices**: Distributed monolith when services share implicit contracts across runtimes

---

## Decision

We adopt a **Hybrid Polyglot Architecture with Clean Boundaries and Vertical Slicing**:

### Runtime Separation
- **.NET 8 Control Plane**: Webhook ingestion, auth, DLP, policy, JIRA updates, audit
- **Python 3.11 Reasoning Plane**: LangGraph agents, RAG, LLM calls
- **Communication**: Async messaging (Azure Service Bus) with schema validation

### Data Flow
```
Unidirectional: Raw ticket → .NET (sanitize) → queue → Python (reason) → queue → .NET (validate + act)
```

### Security Model
- **Zero data egress**: Python never sees PII, tokens, or raw enterprise data
- **DLP in .NET**: Redaction before any queue publish
- **Policy enforcement in .NET**: Final validation before JIRA update

### Vertical Slices
Each business capability (IT Support, HR Onboarding) owns:
- Data pipeline (CRM → vector index)
- RAG configuration (chunking, filters)
- Agent graph (LangGraph nodes)
- Evaluation metrics (precision, override rate)

### Observability
- OpenTelemetry spans across both runtimes
- Immutable decision log in Cosmos DB
- Full citation provenance

---

## Consequences

### Positive
✅ **Security**: Compliance boundaries enforced by runtime isolation  
✅ **AI Velocity**: Python teams experiment without touching .NET  
✅ **Operational Resilience**: Async, idempotent, replayable  
✅ **Auditability**: Immutable logs with provenance  
✅ **Team Autonomy**: Vertical slices enable independent evolution

### Negative
⚠️ **Complexity**: Two runtimes to deploy and monitor  
⚠️ **Schema Discipline**: Contracts must be versioned and validated  
⚠️ **Debugging**: Distributed tracing required across languages

### Risks Mitigated
- **Data Leakage**: DLP + runtime isolation prevents PII egress
- **Model Drift**: Vertical slices enable per-domain evaluation
- **Cascading Failures**: Async messaging + DLQs contain errors
- **Audit Failures**: Immutable logs satisfy SOC2/GDPR

---

## Alternatives Considered

### 1. Pure .NET Monolith
- **Pros**: Single runtime, simpler deployment
- **Cons**: No access to LangGraph, LlamaIndex, ChromaDB; AI team forced into C#
- **Verdict**: Rejected — suboptimal AI tooling

### 2. Pure Python Monolith
- **Pros**: Best AI/ML ecosystem
- **Cons**: Weak enterprise integration (OAuth, RBAC, SharePoint Graph)
- **Verdict**: Rejected — security boundaries unclear

### 3. Microservices with Synchronous REST
- **Pros**: Language flexibility
- **Cons**: Chatty, latency buildup, no idempotency, cascading failures
- **Verdict**: Rejected — operational fragility

### 4. Serverless (Azure Functions)
- **Pros**: Auto-scaling, pay-per-use
- **Cons**: Cold starts, state management complexity, no LangGraph support
- **Verdict**: Rejected — poor fit for stateful agent workflows

---

## Implementation Notes

### Development Environment
- **Local**: In-memory queues, mock LLM responses
- **Staging**: Azure Service Bus, Azure AI Search, GPT-4 (low quota)
- **Production**: Managed Identity, Key Vault, Application Insights

### Migration Path
1. Deploy .NET apps to Azure App Service
2. Deploy Python agent to Azure Container Instances
3. Configure Service Bus with Avro schemas
4. Set up Cosmos DB for decision logs
5. Integrate Azure AI Search for vector index

### Success Metrics
- **Latency**: <2s end-to-end (p95)
- **Accuracy**: >85% auto-triage precision
- **Override Rate**: <20% requiring human review
- **Uptime**: 99.9% SLA

---

## References

- Microsoft Copilot Studio architecture patterns
- Google Duet AI security model
- Amazon Q enterprise integration blueprints
- LangGraph multi-agent documentation
- Azure AI Search hybrid search guide

---

## Decision Rationale Summary

This pattern is **not a buzzword cocktail** — it is the **minimal viable architecture** that satisfies:

1. Enterprise security (data never leaves .NET)
2. AI agility (Python agents evolve independently)
3. Operational resilience (async, idempotent, replayable)
4. Auditability (immutable decision logs with provenance)
5. Research scalability (vertical slices enable per-domain experimentation)

**Approved by:** Enterprise Cloud AI Architect (PhD-level design)  
**Review Date:** Annual (or when adding new vertical slices)
