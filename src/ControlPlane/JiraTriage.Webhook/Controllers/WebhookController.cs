using Microsoft.AspNetCore.Mvc;
using JiraTriage.Core.Models;
using JiraTriage.Core.Security;
using JiraTriage.Core.Services;
using System.Security.Cryptography;
using System.Text;

namespace JiraTriage.Webhook.Controllers;

[ApiController]
[Route("api/[controller]")]
public class WebhookController : ControllerBase
{
    private readonly IQueuePublisher _queuePublisher;
    private readonly ILogger<WebhookController> _logger;

    public WebhookController(IQueuePublisher queuePublisher, ILogger<WebhookController> logger)
    {
        _queuePublisher = queuePublisher;
        _logger = logger;
    }

    [HttpPost]
    public async Task<IActionResult> ReceiveWebhook([FromBody] JiraWebhookEvent webhookEvent)
    {
        try
        {
            _logger.LogInformation("Received webhook: {EventType}", webhookEvent.WebhookEvent);

            if (webhookEvent.Issue == null)
            {
                return BadRequest("Invalid webhook payload: missing issue");
            }

            var summary = webhookEvent.Issue.Fields?.Summary ?? "No summary";
            var description = webhookEvent.Issue.Fields?.Description ?? "No description";

            var (sanitizedSummary, summaryFlags) = DlpRedactor.RedactSensitiveData(summary);
            var (sanitizedDescription, descFlags) = DlpRedactor.RedactSensitiveData(description);

            var allFlags = summaryFlags.Concat(descFlags).Distinct().ToList();

            var reporterEmail = webhookEvent.Issue.Fields?.Reporter?.EmailAddress;
            if (reporterEmail != null && DlpRedactor.HasExternalEmail(reporterEmail))
            {
                allFlags.Add("external_email");
            }

            var sanitizedTicket = new SanitizedTicket
            {
                TicketId = webhookEvent.Issue.Id ?? Guid.NewGuid().ToString(),
                IssueKey = webhookEvent.Issue.Key ?? "UNKNOWN",
                Summary = sanitizedSummary,
                Description = sanitizedDescription,
                IssueType = webhookEvent.Issue.Fields?.IssueType?.Name,
                Priority = webhookEvent.Issue.Fields?.Priority?.Name,
                Reporter = webhookEvent.Issue.Fields?.Reporter?.DisplayName,
                CreatedAt = webhookEvent.Issue.Fields?.Created ?? DateTime.UtcNow,
                RedactionFlags = allFlags,
                SanitizedInputHash = ComputeHash(sanitizedSummary + sanitizedDescription)
            };

            await _queuePublisher.PublishAsync("ticket-sanitized", sanitizedTicket);

            _logger.LogInformation("Sanitized ticket {IssueKey} published to queue", sanitizedTicket.IssueKey);

            return Ok(new { message = "Webhook processed successfully", issueKey = sanitizedTicket.IssueKey });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing webhook");
            return StatusCode(500, "Internal server error");
        }
    }

    [HttpGet("health")]
    public IActionResult Health()
    {
        return Ok(new { status = "healthy", timestamp = DateTime.UtcNow });
    }

    private static string ComputeHash(string input)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(input));
        return Convert.ToHexString(bytes);
    }
}
