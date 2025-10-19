using JiraTriage.Core.Models;
using JiraTriage.Core.Security;
using JiraTriage.Core.Services;
using System.Text.Json;

namespace JiraTriage.Worker.Workers;

public class TicketEnrichmentWorker : BackgroundService
{
    private readonly ILogger<TicketEnrichmentWorker> _logger;
    private readonly HttpClient _httpClient;
    private const string PythonAgentUrl = "http://127.0.0.1:8001/process_ticket";
    private const double ConfidenceThreshold = 0.7;

    public TicketEnrichmentWorker(ILogger<TicketEnrichmentWorker> logger, IHttpClientFactory httpClientFactory)
    {
        _logger = logger;
        _httpClient = httpClientFactory.CreateClient();
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Ticket Enrichment Worker started at: {time}", DateTimeOffset.Now);

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                if (InMemoryQueuePublisher.TryDequeue("ticket-sanitized", out var message) && message != null)
                {
                    var sanitizedTicket = JsonSerializer.Deserialize<SanitizedTicket>(message);
                    if (sanitizedTicket != null)
                    {
                        await ProcessTicketAsync(sanitizedTicket, stoppingToken);
                    }
                }
                else
                {
                    await Task.Delay(1000, stoppingToken);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in worker loop");
                await Task.Delay(5000, stoppingToken);
            }
        }
    }

    private async Task ProcessTicketAsync(SanitizedTicket ticket, CancellationToken cancellationToken)
    {
        try
        {
            _logger.LogInformation("Processing ticket {IssueKey}", ticket.IssueKey);

            var jsonContent = JsonSerializer.Serialize(ticket, new JsonSerializerOptions 
            { 
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase 
            });
            var content = new StringContent(jsonContent, System.Text.Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync(PythonAgentUrl, content, cancellationToken);

            if (response.IsSuccessStatusCode)
            {
                var resultJson = await response.Content.ReadAsStringAsync(cancellationToken);
                var result = JsonSerializer.Deserialize<EnrichedTicketResult>(resultJson, new JsonSerializerOptions 
                { 
                    PropertyNamingPolicy = JsonNamingPolicy.CamelCase 
                });

                if (result != null)
                {
                    var requiresReview = PolicyChecker.RequiresHumanReview(ticket, result);
                    result.RequiresHumanReview = requiresReview;

                    if (requiresReview)
                    {
                        _logger.LogInformation("Ticket {IssueKey} requires human review (Confidence: {Confidence})", 
                            ticket.IssueKey, result.Confidence);
                        await EnqueueForHumanReviewAsync(ticket, result);
                    }
                    else
                    {
                        _logger.LogInformation("Auto-processing ticket {IssueKey} (Confidence: {Confidence})", 
                            ticket.IssueKey, result.Confidence);
                        await UpdateJiraTicketAsync(ticket, result);
                    }

                    await LogDecisionAsync(ticket, result);
                }
            }
            else
            {
                _logger.LogError("Failed to call Python agent: {StatusCode}", response.StatusCode);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing ticket {IssueKey}", ticket.IssueKey);
        }
    }

    private Task EnqueueForHumanReviewAsync(SanitizedTicket ticket, EnrichedTicketResult result)
    {
        _logger.LogInformation("Enqueueing ticket {IssueKey} for human review", ticket.IssueKey);
        return Task.CompletedTask;
    }

    private Task UpdateJiraTicketAsync(SanitizedTicket ticket, EnrichedTicketResult result)
    {
        _logger.LogInformation("Would update JIRA ticket {IssueKey}: Team={Team}, Priority={Priority}", 
            ticket.IssueKey, 
            result.Classification?.Team ?? "Unknown", 
            result.Classification?.SuggestedPriority ?? "Unknown");
        return Task.CompletedTask;
    }

    private Task LogDecisionAsync(SanitizedTicket ticket, EnrichedTicketResult result)
    {
        var decisionLog = new DecisionLogEntry
        {
            EventId = Guid.NewGuid().ToString(),
            JiraIssueKey = ticket.IssueKey,
            Timestamp = DateTime.UtcNow,
            SanitizedInputHash = ticket.SanitizedInputHash ?? "",
            VerticalSlice = result.Classification?.Department ?? "Unknown",
            Classification = result.Classification,
            GeneratedComment = result.GeneratedComment,
            Citations = result.Citations,
            PolicyFlags = result.PolicyFlags,
            ActionTaken = result.RequiresHumanReview ? "human_review" : "auto_update",
            ModelUsed = result.ModelUsed,
            LatencyMs = result.LatencyMs,
            Confidence = result.Confidence
        };

        _logger.LogInformation("Decision logged for {IssueKey}: Action={Action}, Confidence={Confidence}", 
            ticket.IssueKey, decisionLog.ActionTaken, decisionLog.Confidence);
        
        return Task.CompletedTask;
    }
}
