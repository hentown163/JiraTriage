namespace JiraTriage.Core.Models;

public class EnrichedTicketResult
{
    public required string TicketId { get; set; }
    public required string IssueKey { get; set; }
    public Classification? Classification { get; set; }
    public string? GeneratedComment { get; set; }
    public List<string> Citations { get; set; } = new();
    public List<string> PolicyFlags { get; set; } = new();
    public double Confidence { get; set; }
    public string? ModelUsed { get; set; }
    public int LatencyMs { get; set; }
    public bool RequiresHumanReview { get; set; }
}

public class Classification
{
    public string? Department { get; set; }
    public string? Team { get; set; }
    public string? SuggestedPriority { get; set; }
    public string? SuggestedAssignee { get; set; }
    public double Confidence { get; set; }
}
