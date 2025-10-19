using Microsoft.AspNetCore.Mvc.RazorPages;

namespace JiraTriage.UI.Pages;

public class IndexModel : PageModel
{
    private readonly ILogger<IndexModel> _logger;

    public IndexModel(ILogger<IndexModel> logger)
    {
        _logger = logger;
    }

    public int PendingReviews { get; set; }
    public int AutoProcessedToday { get; set; }

    public void OnGet()
    {
        PendingReviews = 0;
        AutoProcessedToday = 0;
    }
}
