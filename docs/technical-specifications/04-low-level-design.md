# Low-Level Design (LLD) - JIRA Triage Agent Platform

**Document Version:** 1.0  
**Last Updated:** October 20, 2025  
**Scope:** Detailed implementation specifications for all components

---

## Executive Summary

This Low-Level Design (LLD) document provides comprehensive implementation details for the JIRA Triage Agent Platform, including class diagrams, sequence diagrams, API specifications, data models, and algorithmic logic. This document serves as the primary reference for developers implementing features and maintenance teams debugging production issues.

---

## 1. Control Plane Implementation (.NET 8)

### 1.1 JiraTriage.Webhook Component

#### 1.1.1 Project Structure

```
JiraTriage.Webhook/
├── Program.cs                      # Application entry point
├── Controllers/
│   └── WebhookController.cs        # Webhook endpoint
├── Models/
│   ├── WebhookRequest.cs          # Incoming webhook payload
│   ├── JiraIssue.cs               # JIRA issue structure
│   └── SanitizedTicket.cs         # Redacted ticket output
├── Services/
│   ├── JiraApiClient.cs           # JIRA REST API wrapper
│   ├── DlpRedactionService.cs     # PII redaction
│   ├── WebhookValidator.cs        # Signature validation
│   └── ServiceBusPublisher.cs     # Queue message publishing
├── appsettings.json               # Configuration
└── JiraTriage.Webhook.csproj      # Project file
```

#### 1.1.2 WebhookController Implementation

```csharp
using Microsoft.AspNetCore.Mvc;
using System.Security.Cryptography;
using System.Text;

namespace JiraTriage.Webhook.Controllers;

[ApiController]
[Route("api/[controller]")]
public class WebhookController : ControllerBase
{
    private readonly ILogger<WebhookController> _logger;
    private readonly WebhookValidator _validator;
    private readonly JiraApiClient _jiraClient;
    private readonly DlpRedactionService _dlpService;
    private readonly ServiceBusPublisher _publisher;
    private readonly IConfiguration _config;

    public WebhookController(
        ILogger<WebhookController> logger,
        WebhookValidator validator,
        JiraApiClient jiraClient,
        DlpRedactionService dlpService,
        ServiceBusPublisher publisher,
        IConfiguration config)
    {
        _logger = logger;
        _validator = validator;
        _jiraClient = jiraClient;
        _dlpService = dlpService;
        _publisher = publisher;
        _config = config;
    }

    [HttpPost]
    public async Task<IActionResult> ProcessWebhook(
        [FromBody] WebhookRequest request,
        [FromHeader(Name = "X-Hub-Signature")] string? signature)
    {
        var requestId = Guid.NewGuid().ToString();
        _logger.LogInformation(
            "Webhook received - RequestId: {RequestId}, Event: {Event}, IssueKey: {IssueKey}",
            requestId, request.WebhookEvent, request.Issue?.Key);

        // Step 1: Validate signature
        if (!_validator.ValidateSignature(request, signature, _config["JIRA_WEBHOOK_SECRET"]!))
        {
            _logger.LogWarning("Invalid webhook signature - RequestId: {RequestId}", requestId);
            return Unauthorized(new { error = "Invalid signature" });
        }

        // Step 2: Filter event type
        if (request.WebhookEvent != "jira:issue_created")
        {
            _logger.LogInformation("Ignored event type: {Event}", request.WebhookEvent);
            return Ok(new { status = "ignored" });
        }

        // Step 3: Fetch full issue details from JIRA API
        var fullIssue = await _jiraClient.GetIssueAsync(request.Issue!.Key);
        if (fullIssue == null)
        {
            _logger.LogError("Failed to fetch issue {IssueKey} from JIRA", request.Issue.Key);
            return StatusCode(500, new { error = "Failed to fetch issue from JIRA" });
        }

        // Step 4: Redact PII
        var sanitized = await _dlpService.RedactPiiAsync(fullIssue);
        
        // Step 5: Publish to Service Bus
        await _publisher.PublishAsync("sanitized-tickets", sanitized);

        _logger.LogInformation(
            "Ticket processed - RequestId: {RequestId}, TicketId: {TicketId}, RedactedEntities: {Count}",
            requestId, sanitized.TicketId, sanitized.RedactedEntities.Count);

        return Accepted(new { ticketId = sanitized.TicketId, status = "processing" });
    }

    [HttpGet("health")]
    public async Task<IActionResult> HealthCheck()
    {
        var health = new
        {
            status = "healthy",
            jiraConnectivity = await _jiraClient.CheckConnectivityAsync(),
            serviceBusConnectivity = await _publisher.CheckConnectivityAsync()
        };
        
        return Ok(health);
    }
}
```

#### 1.1.3 WebhookValidator Implementation

```csharp
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace JiraTriage.Webhook.Services;

public class WebhookValidator
{
    public bool ValidateSignature(WebhookRequest request, string? providedSignature, string secret)
    {
        if (string.IsNullOrEmpty(providedSignature))
            return false;

        // Serialize request to JSON
        var payload = JsonSerializer.Serialize(request);
        var payloadBytes = Encoding.UTF8.GetBytes(payload);
        var secretBytes = Encoding.UTF8.GetBytes(secret);

        // Compute HMAC-SHA256
        using var hmac = new HMACSHA256(secretBytes);
        var hash = hmac.ComputeHash(payloadBytes);
        var computedSignature = "sha256=" + BitConverter.ToString(hash).Replace("-", "").ToLower();

        // Constant-time comparison to prevent timing attacks
        return CryptographicOperations.FixedTimeEquals(
            Encoding.UTF8.GetBytes(computedSignature),
            Encoding.UTF8.GetBytes(providedSignature));
    }
}
```

#### 1.1.4 JiraApiClient Implementation

```csharp
using System.Net.Http.Headers;
using System.Text.Json;

namespace JiraTriage.Webhook.Services;

public class JiraApiClient
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<JiraApiClient> _logger;
    private readonly string _baseUrl;
    private readonly string _apiToken;

    public JiraApiClient(HttpClient httpClient, IConfiguration config, ILogger<JiraApiClient> logger)
    {
        _httpClient = httpClient;
        _logger = logger;
        _baseUrl = config["JIRA_BASE_URL"]!;
        _apiToken = config["JIRA_API_TOKEN"]!;

        // Configure authentication
        var credentials = Convert.ToBase64String(
            Encoding.UTF8.GetBytes($"{config["JIRA_EMAIL"]}:{_apiToken}"));
        _httpClient.DefaultRequestHeaders.Authorization = 
            new AuthenticationHeaderValue("Basic", credentials);
    }

    public async Task<JiraIssue?> GetIssueAsync(string issueKey)
    {
        try
        {
            var response = await _httpClient.GetAsync(
                $"{_baseUrl}/rest/api/3/issue/{issueKey}?expand=renderedFields");
            
            response.EnsureSuccessStatusCode();
            
            var json = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<JiraIssue>(json);
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "Failed to fetch issue {IssueKey}", issueKey);
            return null;
        }
    }

    public async Task<bool> UpdateIssueAsync(string issueKey, JiraUpdate update)
    {
        try
        {
            var content = new StringContent(
                JsonSerializer.Serialize(update),
                Encoding.UTF8,
                "application/json");

            var response = await _httpClient.PutAsync(
                $"{_baseUrl}/rest/api/3/issue/{issueKey}", content);

            return response.IsSuccessStatusCode;
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "Failed to update issue {IssueKey}", issueKey);
            return false;
        }
    }

    public async Task<bool> AddCommentAsync(string issueKey, string commentBody)
    {
        try
        {
            var payload = new { body = new { type = "doc", version = 1, content = new[] {
                new { type = "paragraph", content = new[] {
                    new { type = "text", text = commentBody }
                }}
            }}};

            var content = new StringContent(
                JsonSerializer.Serialize(payload),
                Encoding.UTF8,
                "application/json");

            var response = await _httpClient.PostAsync(
                $"{_baseUrl}/rest/api/3/issue/{issueKey}/comment", content);

            return response.IsSuccessStatusCode;
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "Failed to add comment to {IssueKey}", issueKey);
            return false;
        }
    }

    public async Task<bool> CheckConnectivityAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync($"{_baseUrl}/rest/api/3/myself");
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }
}
```

#### 1.1.5 DlpRedactionService Implementation

```csharp
using System.Diagnostics;

namespace JiraTriage.Webhook.Services;

public class DlpRedactionService
{
    private readonly ILogger<DlpRedactionService> _logger;

    public DlpRedactionService(ILogger<DlpRedactionService> logger)
    {
        _logger = logger;
    }

    public async Task<SanitizedTicket> RedactPiiAsync(JiraIssue issue)
    {
        // Call Python Presidio service via subprocess (development)
        // Production: Use dedicated Presidio API service
        
        var redactedSummary = await RedactTextAsync(issue.Fields.Summary);
        var redactedDescription = await RedactTextAsync(issue.Fields.Description ?? "");
        
        return new SanitizedTicket(
            TicketId: issue.Key,
            Summary: redactedSummary.Text,
            Description: redactedDescription.Text,
            RedactedEntities: redactedSummary.Entities.Concat(redactedDescription.Entities).ToList(),
            Metadata: new TicketMetadata(
                IssueType: issue.Fields.IssueType.Name,
                Priority: issue.Fields.Priority?.Name ?? "Medium",
                ReporterEmail: issue.Fields.Reporter.EmailAddress,
                CreatedAt: issue.Fields.Created
            )
        );
    }

    private async Task<(string Text, List<RedactionFlag> Entities)> RedactTextAsync(string text)
    {
        // Simplified implementation - calls Python Presidio
        // In production, this would be an HTTP call to a dedicated service
        
        var startInfo = new ProcessStartInfo
        {
            FileName = "python",
            Arguments = $"-c \"from presidio_analyzer import AnalyzerEngine; from presidio_anonymizer import AnonymizerEngine; analyzer = AnalyzerEngine(); anonymizer = AnonymizerEngine(); results = analyzer.analyze(text='{text.Replace("'", "\\'")}', language='en'); anonymized = anonymizer.anonymize(text='{text.Replace("'", "\\'")}', analyzer_results=results); print(anonymized.text)\"",
            RedirectStandardOutput = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        using var process = Process.Start(startInfo);
        if (process == null)
        {
            _logger.LogError("Failed to start Presidio process");
            return (text, new List<RedactionFlag>());
        }

        var redactedText = await process.StandardOutput.ReadToEndAsync();
        await process.WaitForExitAsync();

        // Parse redaction entities (simplified - actual implementation parses JSON)
        var entities = new List<RedactionFlag>();
        // ... entity parsing logic ...

        return (redactedText.Trim(), entities);
    }
}

public record RedactionFlag(string EntityType, int Start, int End, string OriginalText);
```

#### 1.1.6 ServiceBusPublisher Implementation

```csharp
using Azure.Messaging.ServiceBus;
using System.Text.Json;

namespace JiraTriage.Webhook.Services;

public class ServiceBusPublisher
{
    private readonly ServiceBusClient _client;
    private readonly ILogger<ServiceBusPublisher> _logger;

    public ServiceBusPublisher(IConfiguration config, ILogger<ServiceBusPublisher> logger)
    {
        var connectionString = config["AZURE_SERVICE_BUS_CONNECTION_STRING"];
        _client = new ServiceBusClient(connectionString);
        _logger = logger;
    }

    public async Task PublishAsync<T>(string queueName, T message)
    {
        var sender = _client.CreateSender(queueName);
        
        try
        {
            var json = JsonSerializer.Serialize(message);
            var serviceBusMessage = new ServiceBusMessage(json)
            {
                ContentType = "application/json",
                MessageId = Guid.NewGuid().ToString(),
                CorrelationId = Activity.Current?.Id // Distributed tracing
            };

            await sender.SendMessageAsync(serviceBusMessage);
            
            _logger.LogInformation(
                "Message published - Queue: {Queue}, MessageId: {MessageId}",
                queueName, serviceBusMessage.MessageId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to publish message to queue {Queue}", queueName);
            throw;
        }
        finally
        {
            await sender.DisposeAsync();
        }
    }

    public async Task<bool> CheckConnectivityAsync()
    {
        try
        {
            var sender = _client.CreateSender("sanitized-tickets");
            await sender.DisposeAsync();
            return true;
        }
        catch
        {
            return false;
        }
    }
}
```

---

### 1.2 JiraTriage.Worker Component

#### 1.2.1 TicketEnrichmentWorker Implementation

```csharp
using Azure.Messaging.ServiceBus;
using Microsoft.Extensions.Hosting;

namespace JiraTriage.Worker.Workers;

public class TicketEnrichmentWorker : BackgroundService
{
    private readonly ILogger<TicketEnrichmentWorker> _logger;
    private readonly ServiceBusClient _serviceBusClient;
    private readonly PolicyEngine _policyEngine;
    private readonly JiraApiClient _jiraClient;
    private readonly DecisionLogger _decisionLogger;
    private readonly IConfiguration _config;

    public TicketEnrichmentWorker(
        ILogger<TicketEnrichmentWorker> logger,
        ServiceBusClient serviceBusClient,
        PolicyEngine policyEngine,
        JiraApiClient jiraClient,
        DecisionLogger decisionLogger,
        IConfiguration config)
    {
        _logger = logger;
        _serviceBusClient = serviceBusClient;
        _policyEngine = policyEngine;
        _jiraClient = jiraClient;
        _decisionLogger = decisionLogger;
        _config = config;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Ticket Enrichment Worker started at: {Time}", DateTimeOffset.Now);

        var processor = _serviceBusClient.CreateProcessor(
            "enriched-tickets",
            new ServiceBusProcessorOptions
            {
                MaxConcurrentCalls = 10,
                AutoCompleteMessages = false,
                MaxAutoLockRenewalDuration = TimeSpan.FromMinutes(5)
            });

        processor.ProcessMessageAsync += MessageHandler;
        processor.ProcessErrorAsync += ErrorHandler;

        await processor.StartProcessingAsync(stoppingToken);

        // Wait until cancellation is requested
        await Task.Delay(Timeout.Infinite, stoppingToken);

        await processor.StopProcessingAsync();
    }

    private async Task MessageHandler(ProcessMessageEventArgs args)
    {
        var messageBody = args.Message.Body.ToString();
        _logger.LogInformation("Processing message: {MessageId}", args.Message.MessageId);

        try
        {
            var enrichedTicket = JsonSerializer.Deserialize<EnrichedTicket>(messageBody);
            if (enrichedTicket == null)
            {
                _logger.LogError("Failed to deserialize message");
                await args.DeadLetterMessageAsync(args.Message, "Deserialization failed");
                return;
            }

            // Apply policy rules
            var decision = _policyEngine.EvaluateTicket(enrichedTicket);

            if (decision.ShouldAutoAssign)
            {
                // Auto-assign path
                var success = await _jiraClient.UpdateIssueAsync(
                    enrichedTicket.TicketId,
                    new JiraUpdate
                    {
                        Assignee = enrichedTicket.AssigneeId,
                        Labels = new List<string> { enrichedTicket.Department, "ai-triaged" }
                    });

                if (success)
                {
                    await _jiraClient.AddCommentAsync(
                        enrichedTicket.TicketId,
                        $"🤖 AI Triage: {enrichedTicket.Justification}\n\n" +
                        $"Confidence: {enrichedTicket.Confidence:P0}\n" +
                        $"Department: {enrichedTicket.Department}");
                }

                await _decisionLogger.LogDecisionAsync(enrichedTicket, decision, null);
            }
            else
            {
                // Human review path
                await _decisionLogger.LogPendingReviewAsync(enrichedTicket, decision.Reason);
            }

            // Complete the message
            await args.CompleteMessageAsync(args.Message);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing message {MessageId}", args.Message.MessageId);
            await args.AbandonMessageAsync(args.Message);
        }
    }

    private Task ErrorHandler(ProcessErrorEventArgs args)
    {
        _logger.LogError(args.Exception, "Service Bus error - Source: {Source}", args.ErrorSource);
        return Task.CompletedTask;
    }
}
```

#### 1.2.2 PolicyEngine Implementation

```csharp
namespace JiraTriage.Worker.Services;

public class PolicyEngine
{
    private const double DefaultConfidenceThreshold = 0.7;

    public PolicyDecision EvaluateTicket(EnrichedTicket ticket)
    {
        var reasons = new List<string>();

        // Rule 1: Confidence threshold
        if (ticket.Confidence < DefaultConfidenceThreshold)
        {
            reasons.Add($"Low confidence ({ticket.Confidence:P0} < {DefaultConfidenceThreshold:P0})");
        }

        // Rule 2: External email detection
        if (IsExternalEmail(ticket.ReporterEmail))
        {
            reasons.Add("External reporter email detected");
        }

        // Rule 3: SLA prediction
        if (ticket.EstimatedSlaDeadline < DateTime.UtcNow.AddHours(2))
        {
            reasons.Add("Critical SLA deadline approaching");
        }

        var shouldAutoAssign = reasons.Count == 0;

        return new PolicyDecision(
            ShouldAutoAssign: shouldAutoAssign,
            Reason: shouldAutoAssign ? "All policy checks passed" : string.Join("; ", reasons)
        );
    }

    private bool IsExternalEmail(string email)
    {
        var allowedDomains = new[] { "@company.com", "@company.net" };
        return !allowedDomains.Any(domain => email.EndsWith(domain, StringComparison.OrdinalIgnoreCase));
    }
}

public record PolicyDecision(bool ShouldAutoAssign, string Reason);
```

#### 1.2.3 DecisionLogger (Cosmos DB)

```csharp
using Azure.Cosmos;

namespace JiraTriage.Worker.Services;

public class DecisionLogger
{
    private readonly CosmosClient _cosmosClient;
    private readonly Container _container;
    private readonly ILogger<DecisionLogger> _logger;

    public DecisionLogger(IConfiguration config, ILogger<DecisionLogger> logger)
    {
        var connectionString = config["AZURE_COSMOS_CONNECTION_STRING"];
        _cosmosClient = new CosmosClient(connectionString);
        _container = _cosmosClient.GetContainer("JiraTriageDB", "DecisionLogs");
        _logger = logger;
    }

    public async Task LogDecisionAsync(
        EnrichedTicket ticket,
        PolicyDecision decision,
        HumanOverride? humanOverride)
    {
        var logEntry = new
        {
            id = Guid.NewGuid().ToString(),
            ticketId = ticket.TicketId,
            timestamp = DateTime.UtcNow,
            aiClassification = new
            {
                department = ticket.Department,
                confidence = ticket.Confidence,
                justification = ticket.Justification,
                citations = ticket.KnowledgeBaseCitations
            },
            policyDecision = new
            {
                shouldAutoAssign = decision.ShouldAutoAssign,
                reason = decision.Reason
            },
            humanOverride = humanOverride,
            processingLatency = 0.0  // TODO: Calculate from start timestamp
        };

        try
        {
            await _container.CreateItemAsync(logEntry, new PartitionKey(ticket.TicketId));
            _logger.LogInformation("Decision logged for ticket {TicketId}", ticket.TicketId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to log decision for ticket {TicketId}", ticket.TicketId);
        }
    }

    public async Task LogPendingReviewAsync(EnrichedTicket ticket, string reason)
    {
        // Store in review database (simplified - actual implementation uses separate table)
        _logger.LogInformation(
            "Ticket {TicketId} flagged for review: {Reason}",
            ticket.TicketId, reason);
    }
}

public record HumanOverride(
    string ReviewerId,
    string FinalDepartment,
    string Reason,
    DateTime Timestamp
);
```

---

### 1.3 JiraTriage.UI Component

#### 1.3.1 Razor Page: PendingReviews

**PendingReviews.cshtml:**
```html
@page
@model JiraTriage.UI.Pages.PendingReviewsModel
@{
    ViewData["Title"] = "Pending Reviews";
}

<div class="container">
    <h1>Pending Reviews</h1>
    <p>Tickets flagged for human review due to low confidence or policy violations.</p>

    <table class="table table-hover">
        <thead>
            <tr>
                <th>Ticket ID</th>
                <th>Summary</th>
                <th>AI Department</th>
                <th>Confidence</th>
                <th>Reason Flagged</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            @foreach (var ticket in Model.PendingTickets)
            {
                <tr>
                    <td><a href="/TicketDetail/@ticket.TicketId">@ticket.TicketId</a></td>
                    <td>@ticket.Summary</td>
                    <td>
                        <span class="badge bg-secondary">@ticket.AiDepartment</span>
                    </td>
                    <td>
                        <div class="progress" style="width: 100px;">
                            <div class="progress-bar @(ticket.Confidence >= 0.7 ? "bg-success" : "bg-warning")" 
                                 style="width: @(ticket.Confidence * 100)%">
                                @(ticket.Confidence.ToString("P0"))
                            </div>
                        </div>
                    </td>
                    <td><small class="text-muted">@ticket.FlagReason</small></td>
                    <td>
                        <div class="btn-group btn-group-sm">
                            <a href="/TicketDetail/@ticket.TicketId" class="btn btn-primary">Review</a>
                            <button class="btn btn-success" onclick="approveTicket('@ticket.TicketId')">Approve</button>
                        </div>
                    </td>
                </tr>
            }
        </tbody>
    </table>

    @if (!Model.PendingTickets.Any())
    {
        <div class="alert alert-info">
            No tickets pending review. Great job! 🎉
        </div>
    }
</div>

@section Scripts {
    <script>
        async function approveTicket(ticketId) {
            if (!confirm(`Approve AI assignment for ${ticketId}?`)) return;
            
            const response = await fetch(`/api/tickets/${ticketId}/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (response.ok) {
                location.reload();
            } else {
                alert('Failed to approve ticket');
            }
        }
    </script>
}
```

**PendingReviews.cshtml.cs:**
```csharp
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace JiraTriage.UI.Pages;

public class PendingReviewsModel : PageModel
{
    private readonly IReviewRepository _repository;

    public List<PendingTicketDto> PendingTickets { get; set; } = new();

    public PendingReviewsModel(IReviewRepository repository)
    {
        _repository = repository;
    }

    public async Task OnGetAsync()
    {
        PendingTickets = await _repository.GetPendingReviewsAsync();
    }
}

public record PendingTicketDto(
    string TicketId,
    string Summary,
    string AiDepartment,
    double Confidence,
    string FlagReason
);
```

---

## 2. Reasoning Plane Implementation (Python 3.11)

### 2.1 FastAPI Application Structure

```
src/ReasoningPlane/api/
├── main.py                     # FastAPI app entry point
├── langgraph_agent.py          # LangGraph workflow
├── enhanced_policy_engine.py   # Policy validation
├── azure_ai_search.py          # RAG retrieval
├── azure_cosmos.py             # Decision logging
├── azure_keyvault.py           # Secret management
├── dlp_engine.py               # Presidio wrapper
├── observability.py            # Application Insights logging
├── connectors/
│   ├── __init__.py
│   ├── confluence_connector.py
│   └── sharepoint_connector.py
└── tests/
    └── test_integration.py
```

### 2.2 main.py (FastAPI Entry Point)

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import logging
from langgraph_agent import TicketClassificationAgent
from observability import setup_observability

# Initialize observability
setup_observability()
logger = logging.getLogger(__name__)

app = FastAPI(title="JIRA Triage Agent API", version="1.0.0")

# Initialize agent
agent = TicketClassificationAgent()

class TicketRequest(BaseModel):
    ticket_id: str = Field(..., min_length=1)
    summary: str
    description: str
    metadata: dict

class Citation(BaseModel):
    title: str
    url: str
    source: str  # "Confluence", "SharePoint", etc.
    relevance_score: float

class TicketResponse(BaseModel):
    ticket_id: str
    department: str
    assignee_id: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    justification: str
    knowledge_base_citations: List[Citation]
    estimated_sla_deadline: str
    processing_time_seconds: float

@app.post("/agent/process", response_model=TicketResponse)
async def process_ticket(request: TicketRequest) -> TicketResponse:
    """
    Process a sanitized JIRA ticket through the LangGraph agent workflow.
    
    Workflow:
    1. ClassifyNode: Determine department assignment
    2. RetrieveNode: Fetch relevant KB articles (RAG)
    3. GenerateNode: Generate justification with citations
    4. PolicyNode: Validate confidence threshold
    """
    logger.info(f"Processing ticket: {request.ticket_id}")
    
    try:
        result = await agent.invoke({
            "ticket_id": request.ticket_id,
            "summary": request.summary,
            "description": request.description,
            "metadata": request.metadata
        })
        
        logger.info(
            f"Ticket processed: {request.ticket_id}, "
            f"Department: {result['department']}, "
            f"Confidence: {result['confidence']:.2f}"
        )
        
        return TicketResponse(**result)
    
    except Exception as e:
        logger.error(f"Error processing ticket {request.ticket_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer."""
    return {
        "status": "healthy",
        "azure_openai": await agent.check_llm_connectivity(),
        "azure_ai_search": await agent.check_search_connectivity()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, workers=4)
```

### 2.3 langgraph_agent.py (Multi-Agent Workflow)

```python
from langgraph.graph import StateGraph, END
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from typing import TypedDict, List
import os
from azure_ai_search import AzureAISearchClient
from enhanced_policy_engine import PolicyEngine

class AgentState(TypedDict):
    ticket_id: str
    summary: str
    description: str
    metadata: dict
    department: str
    confidence: float
    assignee_id: str
    justification: str
    kb_articles: List[dict]
    citations: List[dict]
    policy_passed: bool

class TicketClassificationAgent:
    def __init__(self):
        # Initialize LLM
        self.llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version="2024-05-01-preview",
            deployment_name="gpt-4-turbo",
            temperature=0.3
        )
        
        # Initialize embeddings
        self.embeddings = AzureOpenAIEmbeddings(
            model="text-embedding-3-small",
            dimensions=1536
        )
        
        # Initialize search client
        self.search_client = AzureAISearchClient()
        
        # Initialize policy engine
        self.policy_engine = PolicyEngine()
        
        # Build LangGraph workflow
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("classify", self.classify_node)
        workflow.add_node("retrieve", self.retrieve_node)
        workflow.add_node("generate", self.generate_node)
        workflow.add_node("policy", self.policy_node)
        
        # Add edges
        workflow.set_entry_point("classify")
        workflow.add_edge("classify", "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", "policy")
        workflow.add_edge("policy", END)
        
        return workflow.compile()
    
    async def classify_node(self, state: AgentState) -> AgentState:
        """
        Classify ticket into department using LLM with few-shot examples.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a JIRA ticket triage expert. Classify tickets into departments.
            
Departments:
- IT-DBA: Database issues, connection errors, query performance
- IT-DevOps: Deployment, CI/CD, infrastructure
- IT-Security: Access control, vulnerabilities, compliance
- HR-Onboarding: New employee setup, account creation
- HR-Payroll: Salary, benefits, tax forms
- Finance-AP: Vendor payments, invoices
- Legal-Contracts: Contract review, negotiations

Examples:
Ticket: "Database timeout on staging server"
Department: IT-DBA
Confidence: 0.95

Ticket: "Need access to production servers"
Department: IT-Security
Confidence: 0.85

Ticket: "New hire needs laptop and email setup"
Department: HR-Onboarding
Confidence: 0.90
"""),
            ("user", "Ticket Summary: {summary}\nTicket Description: {description}\n\nClassify this ticket.")
        ])
        
        messages = prompt.format_messages(
            summary=state["summary"],
            description=state["description"]
        )
        
        response = await self.llm.ainvoke(messages)
        
        # Parse response (simplified - actual implementation uses structured output)
        department = "IT-DBA"  # Placeholder
        confidence = 0.85  # Placeholder
        
        state["department"] = department
        state["confidence"] = confidence
        state["assignee_id"] = self._lookup_assignee(department)
        
        return state
    
    async def retrieve_node(self, state: AgentState) -> AgentState:
        """
        Retrieve relevant knowledge base articles using Azure AI Search.
        """
        query = f"{state['summary']} {state['description']}"
        query_embedding = await self.embeddings.aembed_query(query)
        
        results = await self.search_client.hybrid_search(
            query_text=query,
            query_vector=query_embedding,
            department_filter=state["department"],
            top_k=5
        )
        
        state["kb_articles"] = results
        return state
    
    async def generate_node(self, state: AgentState) -> AgentState:
        """
        Generate justification text with KB citations using LLM.
        """
        kb_context = "\n\n".join([
            f"Article: {article['title']}\n{article['content'][:500]}..."
            for article in state["kb_articles"]
        ])
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a JIRA triage assistant. Generate a brief justification
for the department assignment using the knowledge base articles.

Format:
"This ticket should be assigned to [DEPARTMENT] because [REASON].
Based on [ARTICLE TITLE], [SPECIFIC EVIDENCE]."
"""),
            ("user", "Ticket: {summary}\nDepartment: {department}\n\nKnowledge Base:\n{kb_context}\n\nGenerate justification:")
        ])
        
        messages = prompt.format_messages(
            summary=state["summary"],
            department=state["department"],
            kb_context=kb_context
        )
        
        response = await self.llm.ainvoke(messages)
        state["justification"] = response.content
        
        # Extract citations
        state["citations"] = [
            {
                "title": article["title"],
                "url": article["url"],
                "source": article["source"],
                "relevance_score": article["score"]
            }
            for article in state["kb_articles"]
        ]
        
        return state
    
    async def policy_node(self, state: AgentState) -> AgentState:
        """
        Validate policy rules (confidence threshold, business rules).
        """
        policy_result = self.policy_engine.evaluate(
            confidence=state["confidence"],
            department=state["department"],
            metadata=state["metadata"]
        )
        
        state["policy_passed"] = policy_result["passed"]
        return state
    
    async def invoke(self, inputs: dict) -> dict:
        """
        Execute the full workflow and return enriched ticket.
        """
        import time
        start_time = time.time()
        
        result = await self.workflow.ainvoke(inputs)
        
        processing_time = time.time() - start_time
        
        return {
            "ticket_id": result["ticket_id"],
            "department": result["department"],
            "assignee_id": result["assignee_id"],
            "confidence": result["confidence"],
            "justification": result["justification"],
            "knowledge_base_citations": result["citations"],
            "estimated_sla_deadline": self._calculate_sla(result["department"]),
            "processing_time_seconds": processing_time
        }
    
    def _lookup_assignee(self, department: str) -> str:
        """Lookup default assignee for department (from configuration)."""
        assignee_map = {
            "IT-DBA": "user-dba-lead",
            "IT-DevOps": "user-devops-lead",
            "HR-Onboarding": "user-hr-onboarding"
        }
        return assignee_map.get(department, "user-default")
    
    def _calculate_sla(self, department: str) -> str:
        """Calculate estimated SLA deadline based on department."""
        from datetime import datetime, timedelta
        sla_hours = {"IT-DBA": 4, "IT-DevOps": 8, "HR-Onboarding": 24}
        hours = sla_hours.get(department, 24)
        deadline = datetime.utcnow() + timedelta(hours=hours)
        return deadline.isoformat()
    
    async def check_llm_connectivity(self) -> bool:
        try:
            await self.llm.ainvoke("test")
            return True
        except:
            return False
    
    async def check_search_connectivity(self) -> bool:
        return await self.search_client.check_connectivity()
```

### 2.4 azure_ai_search.py (RAG Retrieval)

```python
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
import os

class AzureAISearchClient:
    def __init__(self):
        endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        key = os.getenv("AZURE_SEARCH_KEY")
        
        self.client = SearchClient(
            endpoint=endpoint,
            index_name="ticket-knowledge-base",
            credential=AzureKeyCredential(key)
        )
    
    async def hybrid_search(
        self,
        query_text: str,
        query_vector: List[float],
        department_filter: str,
        top_k: int = 5
    ) -> List[dict]:
        """
        Perform hybrid search (keyword + vector) with department filtering.
        """
        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="embedding"
        )
        
        results = self.client.search(
            search_text=query_text,
            vector_queries=[vector_query],
            filter=f"department eq '{department_filter}'",
            select=["id", "title", "content", "url", "source"],
            top=top_k
        )
        
        return [
            {
                "id": doc["id"],
                "title": doc["title"],
                "content": doc["content"],
                "url": doc["url"],
                "source": doc["source"],
                "score": doc["@search.score"]
            }
            for doc in results
        ]
    
    async def check_connectivity(self) -> bool:
        try:
            _ = self.client.get_document_count()
            return True
        except:
            return False
```

---

## 3. Data Models

### 3.1 .NET Models

```csharp
namespace JiraTriage.Core.Models;

// Webhook payload
public record WebhookRequest(
    string WebhookEvent,
    long Timestamp,
    JiraIssue Issue
);

public record JiraIssue(
    string Id,
    string Key,
    JiraFields Fields
);

public record JiraFields(
    string Summary,
    string? Description,
    IssueType IssueType,
    Priority? Priority,
    Reporter Reporter,
    DateTime Created
);

public record IssueType(string Name);
public record Priority(string Name);
public record Reporter(string AccountId, string DisplayName, string EmailAddress);

// Sanitized ticket (after DLP)
public record SanitizedTicket(
    string TicketId,
    string Summary,
    string Description,
    List<RedactionFlag> RedactedEntities,
    TicketMetadata Metadata
);

public record TicketMetadata(
    string IssueType,
    string Priority,
    string ReporterEmail,
    DateTime CreatedAt
);

// Enriched ticket (from Python agent)
public record EnrichedTicket(
    string TicketId,
    string Department,
    string AssigneeId,
    double Confidence,
    string Justification,
    List<Citation> KnowledgeBaseCitations,
    DateTime EstimatedSlaDeadline
);

public record Citation(
    string Title,
    string Url,
    string Source,
    double RelevanceScore
);

// JIRA update payload
public record JiraUpdate(
    string Assignee,
    List<string> Labels
);
```

### 3.2 Python Models

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class TicketRequest(BaseModel):
    ticket_id: str = Field(..., min_length=1)
    summary: str
    description: str
    metadata: dict

class Citation(BaseModel):
    title: str
    url: str
    source: str
    relevance_score: float

class TicketResponse(BaseModel):
    ticket_id: str
    department: str
    assignee_id: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    justification: str
    knowledge_base_citations: List[Citation]
    estimated_sla_deadline: str
    processing_time_seconds: float
```

---

## 4. API Specifications

### 4.1 Webhook API (.NET)

**Endpoint:** `POST /api/webhook`

**Request Headers:**
```
Content-Type: application/json
X-Hub-Signature: sha256=<hmac-sha256-signature>
```

**Request Body:**
```json
{
  "webhookEvent": "jira:issue_created",
  "timestamp": 1697000000,
  "issue": {
    "id": "10001",
    "key": "PROJ-123",
    "fields": {
      "summary": "Database connection timeout",
      "description": "Can not connect to staging DB",
      "issueType": { "name": "Bug" },
      "priority": { "name": "High" },
      "reporter": {
        "accountId": "user123",
        "displayName": "John Doe",
        "emailAddress": "john@company.com"
      },
      "created": "2025-10-20T10:00:00Z"
    }
  }
}
```

**Response (202 Accepted):**
```json
{
  "ticketId": "PROJ-123",
  "status": "processing"
}
```

### 4.2 Python Agent API

**Endpoint:** `POST /agent/process`

**Request Body:**
```json
{
  "ticket_id": "PROJ-123",
  "summary": "Database connection timeout",
  "description": "Cannot connect to staging database - timeout after 30 seconds",
  "metadata": {
    "issueType": "Bug",
    "priority": "High",
    "reporterEmail": "john@company.com"
  }
}
```

**Response (200 OK):**
```json
{
  "ticket_id": "PROJ-123",
  "department": "IT-DBA",
  "assignee_id": "user-dba-lead",
  "confidence": 0.92,
  "justification": "This ticket should be assigned to IT-DBA because it involves database connectivity issues. Based on KB article 'Troubleshooting Database Timeouts', connection timeouts typically indicate network or authentication problems that require DBA investigation.",
  "knowledge_base_citations": [
    {
      "title": "Troubleshooting Database Timeouts",
      "url": "https://confluence.company.com/display/IT/DB-Timeouts",
      "source": "Confluence",
      "relevance_score": 0.95
    }
  ],
  "estimated_sla_deadline": "2025-10-20T14:00:00Z",
  "processing_time_seconds": 3.2
}
```

---

## 5. Error Handling Patterns

### 5.1 .NET Exception Handling

```csharp
try
{
    await _jiraClient.UpdateIssueAsync(ticketId, update);
}
catch (HttpRequestException ex) when (ex.StatusCode == HttpStatusCode.TooManyRequests)
{
    // Rate limit exceeded - back off and retry
    await Task.Delay(TimeSpan.FromSeconds(60));
    await _jiraClient.UpdateIssueAsync(ticketId, update);  // Retry once
}
catch (HttpRequestException ex)
{
    _logger.LogError(ex, "JIRA API error for ticket {TicketId}", ticketId);
    throw;  // Propagate to dead letter queue
}
```

### 5.2 Python Exception Handling

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def call_azure_openai(prompt: str) -> str:
    try:
        response = await llm.ainvoke(prompt)
        return response.content
    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded, retrying: {e}")
        raise  # Will trigger retry
    except Exception as e:
        logger.error(f"LLM API error: {e}")
        raise
```

---

## Appendix A: Database Schemas

See `docs/technical-specifications/05-database-design.md` for complete database design.

---

## Appendix B: Configuration Files

**appsettings.json (.NET):**
```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning"
    }
  },
  "AllowedHosts": "*",
  "JIRA_BASE_URL": "https://your-company.atlassian.net",
  "JIRA_EMAIL": "bot@company.com",
  "AZURE_SERVICE_BUS_CONNECTION_STRING": "<from-keyvault>",
  "AZURE_COSMOS_CONNECTION_STRING": "<from-keyvault>",
  "JIRA_WEBHOOK_SECRET": "<from-keyvault>"
}
```

**.env (Python):**
```bash
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_API_KEY=<from-keyvault>
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=<from-keyvault>
AZURE_SERVICE_BUS_CONNECTION_STRING=<from-keyvault>
```

---

**Document Control:**
- **Classification:** Internal Implementation Guide
- **Distribution:** Engineering Team
- **Review Schedule:** As needed (code changes)
- **Version:** 1.0 (2025-10-20)
