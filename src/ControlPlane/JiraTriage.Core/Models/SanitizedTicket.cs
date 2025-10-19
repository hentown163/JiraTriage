namespace JiraTriage.Core.Models;

public class SanitizedTicket
{
    public required string TicketId { get; set; }
    public required string IssueKey { get; set; }
    public required string Summary { get; set; }
    public required string Description { get; set; }
    public string? IssueType { get; set; }
    public string? Priority { get; set; }
    public string? Reporter { get; set; }
    public DateTime CreatedAt { get; set; }
    public List<string> RedactionFlags { get; set; } = new();
    public string? SanitizedInputHash { get; set; }
}
