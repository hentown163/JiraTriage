# Deployment Guide - JIRA Triage Agent Platform

## Overview

This document provides comprehensive guidance for deploying the JIRA Triage Agent Platform to production using Azure services.

**Target Architecture**: Azure App Service (.NET) + Azure Container Instances (Python) + Azure Managed Services

---

## Prerequisites

### Azure Resources Required

1. **Azure App Service** (2 instances)
   - JiraTriage.UI (Razor Pages dashboard)
   - JiraTriage.Webhook (JIRA webhook ingestion API)

2. **Azure Container Instances or App Service for Containers**
   - Python Reasoning Plane (Fast API with LangGraph)

3. **Azure Service Bus** (Standard/Premium tier)
   - Topic: `sanitized-tickets`
   - Topic: `enriched-tickets`

4. **Azure Cosmos DB** (SQL API)
   - Database: `JiraTriageDB`
   - Container: `DecisionLogs` (partition key: `/department`)
   - 7-year TTL configured (220752000 seconds)

5. **Azure AI Search** (Standard tier minimum)
   - Index: `jira-kb`
   - Vector search enabled (1536 dimensions for text-embedding-3-small)

6. **Azure Key Vault**
   - Store all API keys and connection strings

7. **Azure OpenAI Service**
   - gpt-5 model deployment
   - text-embedding-3-small deployment

8. **Application Insights**
   - Distributed tracing and monitoring

### Development Requirements

- .NET 8.0 SDK
- Python 3.11+
- Azure CLI
- Docker (for containerization)
- UV or pip for Python package management

---

## Step 1: Azure Resource Provisioning (Week 1)

### 1.1 Resource Group Creation

```bash
az login
az group create --name rg-jira-triage-prod --location eastus
```

### 1.2 Azure Service Bus

```bash
az servicebus namespace create \
  --resource-group rg-jira-triage-prod \
  --name sb-jira-triage-prod \
  --location eastus \
  --sku Standard

az servicebus topic create \
  --resource-group rg-jira-triage-prod \
  --namespace-name sb-jira-triage-prod \
  --name sanitized-tickets

az servicebus topic create \
  --resource-group rg-jira-triage-prod \
  --namespace-name sb-jira-triage-prod \
  --name enriched-tickets
```

### 1.3 Azure Cosmos DB

```bash
az cosmosdb create \
  --name cosmos-jira-triage-prod \
  --resource-group rg-jira-triage-prod \
  --default-consistency-level Session \
  --locations regionName=eastus failoverPriority=0 isZoneRedundant=False \
  --enable-automatic-failover true

az cosmosdb sql database create \
  --account-name cosmos-jira-triage-prod \
  --resource-group rg-jira-triage-prod \
  --name JiraTriageDB

az cosmosdb sql container create \
  --account-name cosmos-jira-triage-prod \
  --resource-group rg-jira-triage-prod \
  --database-name JiraTriageDB \
  --name DecisionLogs \
  --partition-key-path "/department" \
  --default-ttl 220752000
```

### 1.4 Azure AI Search

```bash
az search service create \
  --name search-jira-kb-prod \
  --resource-group rg-jira-triage-prod \
  --sku standard \
  --partition-count 1 \
  --replica-count 2
```

### 1.5 Azure OpenAI

```bash
az cognitiveservices account create \
  --name openai-jira-triage \
  --resource-group rg-jira-triage-prod \
  --kind OpenAI \
  --sku S0 \
  --location eastus

az cognitiveservices account deployment create \
  --name openai-jira-triage \
  --resource-group rg-jira-triage-prod \
  --deployment-name gpt-5 \
  --model-name gpt-5 \
  --model-version "2025-08" \
  --model-format OpenAI \
  --sku-capacity 50 \
  --sku-name Standard

az cognitiveservices account deployment create \
  --name openai-jira-triage \
  --resource-group rg-jira-triage-prod \
  --deployment-name text-embedding-3-small \
  --model-name text-embedding-3-small \
  --model-version "1" \
  --model-format OpenAI \
  --sku-capacity 50 \
  --sku-name Standard
```

### 1.6 Azure Key Vault

```bash
az keyvault create \
  --name kv-jira-triage-prod \
  --resource-group rg-jira-triage-prod \
  --location eastus \
  --enable-rbac-authorization false

az keyvault set-policy \
  --name kv-jira-triage-prod \
  --upn user@company.com \
  --secret-permissions get list set delete
```

### 1.7 Application Insights

```bash
az monitor app-insights component create \
  --app ai-jira-triage \
  --location eastus \
  --resource-group rg-jira-triage-prod \
  --application-type web
```

---

## Step 2: Secret Configuration (Week 1)

### 2.1 Store Secrets in Key Vault

```bash
# OpenAI
az keyvault secret set --vault-name kv-jira-triage-prod \
  --name OpenAI-API-Key --value "your-openai-key"

# Azure Search
SEARCH_KEY=$(az search admin-key show \
  --resource-group rg-jira-triage-prod \
  --service-name search-jira-kb-prod \
  --query primaryKey -o tsv)
az keyvault secret set --vault-name kv-jira-triage-prod \
  --name Azure-Search-API-Key --value "$SEARCH_KEY"

# Cosmos DB
COSMOS_KEY=$(az cosmosdb keys list \
  --name cosmos-jira-triage-prod \
  --resource-group rg-jira-triage-prod \
  --query primaryMasterKey -o tsv)
az keyvault secret set --vault-name kv-jira-triage-prod \
  --name Cosmos-Key --value "$COSMOS_KEY"

# Service Bus
SB_CONN=$(az servicebus namespace authorization-rule keys list \
  --resource-group rg-jira-triage-prod \
  --namespace-name sb-jira-triage-prod \
  --name RootManageSharedAccessKey \
  --query primaryConnectionString -o tsv)
az keyvault secret set --vault-name kv-jira-triage-prod \
  --name ServiceBus-Connection-String --value "$SB_CONN"

# Confluence (if using)
az keyvault secret set --vault-name kv-jira-triage-prod \
  --name Confluence-API-Token --value "your-confluence-token"

# SharePoint / Graph API
az keyvault secret set --vault-name kv-jira-triage-prod \
  --name Azure-Client-Secret --value "your-client-secret"
```

---

## Step 3: Application Deployment (Week 2)

### 3.1 Build .NET Applications

```bash
cd src/ControlPlane/JiraTriage.UI
dotnet publish -c Release -o ./publish

cd ../JiraTriage.Webhook
dotnet publish -c Release -o ./publish

cd ../JiraTriage.Worker
dotnet publish -c Release -o ./publish
```

### 3.2 Create App Services

```bash
# UI Dashboard
az appservice plan create \
  --name asp-jira-triage-prod \
  --resource-group rg-jira-triage-prod \
  --sku B2 \
  --is-linux

az webapp create \
  --resource-group rg-jira-triage-prod \
  --plan asp-jira-triage-prod \
  --name app-jira-triage-ui-prod \
  --runtime "DOTNETCORE:8.0"

# Webhook API
az webapp create \
  --resource-group rg-jira-triage-prod \
  --plan asp-jira-triage-prod \
  --name app-jira-triage-webhook-prod \
  --runtime "DOTNETCORE:8.0"
```

### 3.3 Configure App Settings

```bash
# Get Key Vault URI
KV_URI=$(az keyvault show --name kv-jira-triage-prod \
  --query properties.vaultUri -o tsv)

# Configure UI App
az webapp config appsettings set \
  --resource-group rg-jira-triage-prod \
  --name app-jira-triage-ui-prod \
  --settings \
  AZURE_KEYVAULT_URL="$KV_URI" \
  APPLICATIONINSIGHTS_CONNECTION_STRING="your-app-insights-connection-string"

# Configure Webhook App
az webapp config appsettings set \
  --resource-group rg-jira-triage-prod \
  --name app-jira-triage-webhook-prod \
  --settings \
  AZURE_KEYVAULT_URL="$KV_URI" \
  APPLICATIONINSIGHTS_CONNECTION_STRING="your-app-insights-connection-string"
```

### 3.4 Deploy .NET Applications

```bash
cd src/ControlPlane/JiraTriage.UI/publish
az webapp deploy --resource-group rg-jira-triage-prod \
  --name app-jira-triage-ui-prod \
  --src-path .

cd ../../JiraTriage.Webhook/publish
az webapp deploy --resource-group rg-jira-triage-prod \
  --name app-jira-triage-webhook-prod \
  --src-path .
```

### 3.5 Build and Deploy Python Reasoning Plane

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY src/ReasoningPlane/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ReasoningPlane/api /app/api

EXPOSE 8001

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

```bash
# Build and push to Azure Container Registry
az acr create --resource-group rg-jira-triage-prod \
  --name acrjiratriage --sku Basic

az acr build --registry acrjiratriage \
  --image jira-reasoning-plane:v1 .

# Deploy to Azure Container Instances
az container create \
  --resource-group rg-jira-triage-prod \
  --name aci-reasoning-plane \
  --image acrjiratriage.azurecr.io/jira-reasoning-plane:v1 \
  --cpu 2 --memory 4 \
  --dns-name-label jira-reasoning-plane \
  --ports 8001 \
  --environment-variables \
  OPENAI_API_KEY=@Microsoft.KeyVault(SecretUri=$KV_URI/secrets/OpenAI-API-Key/) \
  AZURE_SEARCH_ENDPOINT="https://search-jira-kb-prod.search.windows.net" \
  COSMOS_ENDPOINT="https://cosmos-jira-triage-prod.documents.azure.com:443/"
```

---

## Step 4: Initialize Azure AI Search Index (Week 2)

### 4.1 Run Index Creation Script

Create a Python script to initialize the search index:

```python
from azure_ai_search import search_manager

# Create index
search_manager.create_index()

# TODO: Load initial knowledge base documents
# This would typically involve:
# 1. Extracting content from Confluence
# 2. Extracting content from SharePoint
# 3. Generating embeddings
# 4. Uploading to Azure AI Search
```

---

## Step 5: Security Configuration (Week 2-3)

### 5.1 Enable Managed Identity

```bash
# Enable system-assigned managed identity for UI app
az webapp identity assign \
  --resource-group rg-jira-triage-prod \
  --name app-jira-triage-ui-prod

# Grant Key Vault access
UI_IDENTITY=$(az webapp identity show \
  --resource-group rg-jira-triage-prod \
  --name app-jira-triage-ui-prod \
  --query principalId -o tsv)

az keyvault set-policy \
  --name kv-jira-triage-prod \
  --object-id $UI_IDENTITY \
  --secret-permissions get list
```

### 5.2 Configure Azure AD Authentication for UI

```bash
az webapp auth update \
  --resource-group rg-jira-triage-prod \
  --name app-jira-triage-ui-prod \
  --enabled true \
  --action LoginWithAzureActiveDirectory \
  --aad-allowed-token-audiences "https://app-jira-triage-ui-prod.azurewebsites.net"
```

### 5.3 JIRA Webhook Signature Validation

Configure webhook signature validation in `JiraTriage.Webhook/appsettings.json`:

```json
{
  "JiraWebhook": {
    "Secret": "@Microsoft.KeyVault(SecretUri=https://kv-jira-triage-prod.vault.azure.net/secrets/JIRA-Webhook-Secret/)"
  }
}
```

---

## Step 6: Testing & Validation (Week 3)

### 6.1 End-to-End Test

1. Configure JIRA webhook to point to: `https://app-jira-triage-webhook-prod.azurewebsites.net/api/webhook`
2. Create test JIRA ticket
3. Verify workflow:
   - Webhook receives event
   - Ticket sanitized and queued
   - Python agent processes ticket
   - Decision logged to Cosmos DB
   - UI displays ticket for review (if flagged)

### 6.2 Load Testing

Use Azure Load Testing service:
- Target: 1000 tickets/hour
- Monitor Application Insights for bottlenecks
- Adjust App Service plan as needed

### 6.3 Security Testing

- Penetration testing
- OWASP Top 10 validation
- Secret scanning
- Compliance audit (SOC 2, GDPR)

---

## Step 7: Monitoring & Observability (Week 3)

### 7.1 Application Insights Dashboards

Create dashboards for:
- Ticket processing latency
- Classification accuracy (confidence distribution)
- Human review queue depth
- SLA compliance metrics
- Error rates by component

### 7.2 Alerts

Configure alerts for:
- High error rate (>5% in 5 minutes)
- Slow processing (P95 latency >10 seconds)
- Queue backlog (>100 tickets pending)
- SLA breach risk (tickets approaching deadline)

---

## Step 8: Production Cutover (Week 4)

### 8.1 Pre-Launch Checklist

- [ ] All Azure resources provisioned and configured
- [ ] Secrets stored in Key Vault
- [ ] Applications deployed and healthy
- [ ] Azure AI Search index populated
- [ ] JIRA webhook configured
- [ ] Azure AD authentication enabled
- [ ] Monitoring dashboards created
- [ ] Runbook documentation completed
- [ ] On-call rotation established
- [ ] Disaster recovery plan documented

### 8.2 Go-Live

1. Enable JIRA webhook in production
2. Monitor first 100 tickets closely
3. Validate human review workflow
4. Gather user feedback
5. Iterate on confidence thresholds

---

## Cost Estimation

**Monthly Azure Costs (Standard Configuration)**:

| Resource | SKU/Tier | Est. Cost |
|----------|----------|-----------|
| App Service Plan (B2) | 2 instances | $150 |
| Container Instances | 2 vCPU, 4GB RAM | $90 |
| Service Bus (Standard) | | $10 |
| Cosmos DB (400 RU/s) | | $25 |
| Azure AI Search (Standard S1) | | $250 |
| Azure OpenAI (GPT-5) | 1M tokens | $200-$500 |
| Key Vault | | $5 |
| Application Insights | | $50 |
| **Total** | | **$780-$1,080/month** |

*Note: OpenAI costs vary significantly based on ticket volume*

---

## Maintenance & Operations

### Daily Tasks
- Monitor Application Insights for errors
- Review human override queue
- Check SLA compliance metrics

### Weekly Tasks
- Review classification accuracy trends
- Analyze human override patterns
- Update knowledge base (Confluence/SharePoint sync)
- Review cost optimization opportunities

### Monthly Tasks
- Security patch deployment
- Disaster recovery drill
- Capacity planning review
- Model performance analysis

---

## Disaster Recovery

**RTO**: 4 hours  
**RPO**: 15 minutes

### Backup Strategy
- Cosmos DB: Continuous backup enabled (30-day retention)
- Azure AI Search: Weekly index snapshots
- Code: GitHub with branch protection
- Secrets: Key Vault soft-delete enabled (90-day recovery)

### Failover Procedure
1. Promote standby region (if configured)
2. Update DNS/Traffic Manager
3. Restore Cosmos DB from backup point-in-time
4. Re-index Azure AI Search if needed
5. Validate end-to-end workflow

---

## Support Contacts

- Azure Support: Open ticket via Azure Portal
- OpenAI Support: platform.openai.com/account/support
- JIRA Support: support.atlassian.com
- Internal Escalation: escalations@company.com

---

## Appendix: Environment Variables Reference

### .NET Applications
```
AZURE_KEYVAULT_URL=https://kv-jira-triage-prod.vault.azure.net/
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=xxx
ASPNETCORE_ENVIRONMENT=Production
```

### Python Application
```
OPENAI_API_KEY=<from Key Vault>
AZURE_SEARCH_ENDPOINT=https://search-jira-kb-prod.search.windows.net
AZURE_SEARCH_API_KEY=<from Key Vault>
COSMOS_ENDPOINT=https://cosmos-jira-triage-prod.documents.azure.com:443/
COSMOS_KEY=<from Key Vault>
AZURE_KEYVAULT_URL=https://kv-jira-triage-prod.vault.azure.net/
CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net
CONFLUENCE_API_TOKEN=<from Key Vault>
AZURE_TENANT_ID=<your-tenant-id>
AZURE_CLIENT_ID=<your-client-id>
AZURE_CLIENT_SECRET=<from Key Vault>
```

---

**Document Version**: 1.0  
**Last Updated**: October 20, 2025  
**Next Review**: January 20, 2026
