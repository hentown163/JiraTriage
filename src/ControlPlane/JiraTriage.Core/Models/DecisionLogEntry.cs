namespace JiraTriage.Core.Models;

public class DecisionLogEntry
{
    public required string EventId { get; set; }
    public required string JiraIssueKey { get; set; }
    public DateTime Timestamp { get; set; }
    public required string SanitizedInputHash { get; set; }
    public string? VerticalSlice { get; set; }
    public Classification? Classification { get; set; }
    public List<string> RetrievedDocIds { get; set; } = new();
    public string? GeneratedComment { get; set; }
    public List<string> Citations { get; set; } = new();
    public List<string> PolicyFlags { get; set; } = new();
    public string? ActionTaken { get; set; }
    public string? ModelUsed { get; set; }
    public int LatencyMs { get; set; }
    public double Confidence { get; set; }
    public string? ReviewedBy { get; set; }
    public DateTime? ReviewedAt { get; set; }
}
