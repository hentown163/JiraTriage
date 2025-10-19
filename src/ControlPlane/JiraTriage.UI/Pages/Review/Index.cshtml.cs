using Microsoft.AspNetCore.Mvc.RazorPages;

namespace JiraTriage.UI.Pages.Review;

public class ReviewIndexModel : PageModel
{
    public List<PendingTicket> PendingTickets { get; set; } = new();

    public void OnGet()
    {
        PendingTickets = new List<PendingTicket>();
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
