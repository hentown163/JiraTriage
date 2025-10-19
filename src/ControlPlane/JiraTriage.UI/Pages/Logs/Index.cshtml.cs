using Microsoft.AspNetCore.Mvc.RazorPages;
using JiraTriage.Core.Services;

namespace JiraTriage.UI.Pages.Logs;

public class LogsIndexModel : PageModel
{
    private readonly DecisionLogService _decisionLogService;

    public LogsIndexModel(DecisionLogService decisionLogService)
    {
        _decisionLogService = decisionLogService;
    }

    public List<DecisionLog> DecisionLogs { get; set; } = new();

    public void OnGet()
    {
        var recentLogs = _decisionLogService.GetRecentLogs();
        DecisionLogs = recentLogs.Select(log => new DecisionLog
        {
            Timestamp = log.Timestamp,
            IssueKey = log.JiraIssueKey,
            Department = log.Classification?.Department ?? "Unknown",
            Team = log.Classification?.Team ?? "Unknown",
            ActionTaken = log.ActionTaken ?? "unknown",
            Confidence = log.Confidence,
            ModelUsed = log.ModelUsed ?? "unknown"
        }).ToList();
    }
}

public class DecisionLog
{
    public DateTime Timestamp { get; set; }
    public string IssueKey { get; set; } = "";
    public string Department { get; set; } = "";
    public string Team { get; set; } = "";
    public string ActionTaken { get; set; } = "";
    public double Confidence { get; set; }
    public string ModelUsed { get; set; } = "";
}
