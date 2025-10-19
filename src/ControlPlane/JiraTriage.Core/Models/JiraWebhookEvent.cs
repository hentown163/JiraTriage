namespace JiraTriage.Core.Models;

public class JiraWebhookEvent
{
    public string? WebhookEvent { get; set; }
    public long Timestamp { get; set; }
    public Issue? Issue { get; set; }
    public User? User { get; set; }
}

public class Issue
{
    public string? Id { get; set; }
    public string? Key { get; set; }
    public Fields? Fields { get; set; }
}

public class Fields
{
    public string? Summary { get; set; }
    public string? Description { get; set; }
    public IssueType? IssueType { get; set; }
    public Priority? Priority { get; set; }
    public User? Reporter { get; set; }
    public User? Assignee { get; set; }
    public DateTime? Created { get; set; }
    public DateTime? Updated { get; set; }
}

public class IssueType
{
    public string? Name { get; set; }
}

public class Priority
{
    public string? Name { get; set; }
}

public class User
{
    public string? AccountId { get; set; }
    public string? EmailAddress { get; set; }
    public string? DisplayName { get; set; }
}
