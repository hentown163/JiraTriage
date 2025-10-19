using JiraTriage.Core.Models;

namespace JiraTriage.Core.Security;

public class PolicyChecker
{
    public static bool RequiresHumanReview(SanitizedTicket ticket, EnrichedTicketResult result)
    {
        if (result.Confidence < 0.7)
            return true;

        if (ticket.RedactionFlags.Contains("email_detected") && 
            ticket.RedactionFlags.Contains("external_email"))
            return true;

        if (result.PolicyFlags.Contains("high_risk") || 
            result.PolicyFlags.Contains("compliance_required"))
            return true;

        if (ticket.RedactionFlags.Any(flag => flag.Contains("ssn") || flag.Contains("credit_card")))
            return true;

        return false;
    }

    public static List<string> ValidatePolicyCompliance(SanitizedTicket ticket)
    {
        var policyFlags = new List<string>();

        if (ticket.RedactionFlags.Contains("email_detected"))
        {
            policyFlags.Add("contains_sensitive_pii");
        }

        if (ticket.Priority?.ToLower() == "highest" || ticket.Priority?.ToLower() == "critical")
        {
            policyFlags.Add("high_priority_ticket");
        }

        return policyFlags;
    }
}
