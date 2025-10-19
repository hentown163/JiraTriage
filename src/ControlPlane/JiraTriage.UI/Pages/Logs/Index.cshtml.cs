using Microsoft.AspNetCore.Mvc.RazorPages;

namespace JiraTriage.UI.Pages.Logs;

public class LogsIndexModel : PageModel
{
    public List<DecisionLog> DecisionLogs { get; set; } = new();

    public void OnGet()
    {
        DecisionLogs = new List<DecisionLog>();
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
