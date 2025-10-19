using Microsoft.AspNetCore.Mvc.RazorPages;
using JiraTriage.Core.Services;

namespace JiraTriage.UI.Pages.Review;

public class ReviewIndexModel : PageModel
{
    private readonly DecisionLogService _decisionLogService;

    public ReviewIndexModel(DecisionLogService decisionLogService)
    {
        _decisionLogService = decisionLogService;
    }

    public List<PendingTicket> PendingTickets { get; set; } = new();

    public void OnGet()
    {
        var pendingReviews = _decisionLogService.GetPendingReviews();
        PendingTickets = pendingReviews.Select(pr => new PendingTicket
        {
            IssueKey = pr.Item1.IssueKey,
            Summary = pr.Item1.Summary,
            Department = pr.Item2.Classification?.Department ?? "Unknown",
            Team = pr.Item2.Classification?.Team ?? "Unknown",
            Confidence = pr.Item2.Confidence,
            PolicyFlags = pr.Item2.PolicyFlags
        }).ToList();
    }
}

public class PendingTicket
{
    public string IssueKey { get; set; } = "";
    public string Summary { get; set; } = "";
    public string Department { get; set; } = "";
    public string Team { get; set; } = "";
    public double Confidence { get; set; }
    public List<string> PolicyFlags { get; set; } = new();
}
