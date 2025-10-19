using JiraTriage.Core.Models;
using System.Collections.Concurrent;

namespace JiraTriage.Core.Services;

public class DecisionLogService
{
    private static readonly ConcurrentBag<DecisionLogEntry> DecisionLogs = new();
    private static readonly ConcurrentBag<(SanitizedTicket, EnrichedTicketResult)> PendingReviews = new();

    public void LogDecision(DecisionLogEntry entry)
    {
        DecisionLogs.Add(entry);
    }

    public void AddPendingReview(SanitizedTicket ticket, EnrichedTicketResult result)
    {
        PendingReviews.Add((ticket, result));
    }

    public List<DecisionLogEntry> GetRecentLogs(int count = 50)
    {
        return DecisionLogs.OrderByDescending(l => l.Timestamp).Take(count).ToList();
    }

    public List<(SanitizedTicket, EnrichedTicketResult)> GetPendingReviews()
    {
        return PendingReviews.ToList();
    }

    public int GetPendingReviewCount()
    {
        return PendingReviews.Count;
    }

    public int GetAutoProcessedTodayCount()
    {
        return DecisionLogs.Count(l => 
            l.Timestamp.Date == DateTime.UtcNow.Date && 
            l.ActionTaken == "auto_update");
    }
}
