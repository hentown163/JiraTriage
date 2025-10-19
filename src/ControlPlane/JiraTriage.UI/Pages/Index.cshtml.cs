using Microsoft.AspNetCore.Mvc.RazorPages;
using JiraTriage.Core.Services;

namespace JiraTriage.UI.Pages;

public class IndexModel : PageModel
{
    private readonly ILogger<IndexModel> _logger;
    private readonly DecisionLogService _decisionLogService;

    public IndexModel(ILogger<IndexModel> logger, DecisionLogService decisionLogService)
    {
        _logger = logger;
        _decisionLogService = decisionLogService;
    }

    public int PendingReviews { get; set; }
    public int AutoProcessedToday { get; set; }

    public void OnGet()
    {
        PendingReviews = _decisionLogService.GetPendingReviewCount();
        AutoProcessedToday = _decisionLogService.GetAutoProcessedTodayCount();
    }
}
