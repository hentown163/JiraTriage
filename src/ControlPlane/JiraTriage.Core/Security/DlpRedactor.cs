using System.Text.RegularExpressions;

namespace JiraTriage.Core.Security;

public class DlpRedactor
{
    private static readonly Regex EmailRegex = new(@"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", RegexOptions.Compiled);
    private static readonly Regex PhoneRegex = new(@"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", RegexOptions.Compiled);
    private static readonly Regex SsnRegex = new(@"\b\d{3}-\d{2}-\d{4}\b", RegexOptions.Compiled);
    private static readonly Regex CreditCardRegex = new(@"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", RegexOptions.Compiled);
    
    public static (string sanitized, List<string> flags) RedactSensitiveData(string input)
    {
        var flags = new List<string>();
        var sanitized = input;

        if (EmailRegex.IsMatch(sanitized))
        {
            flags.Add("email_detected");
            sanitized = EmailRegex.Replace(sanitized, "[EMAIL_REDACTED]");
        }

        if (PhoneRegex.IsMatch(sanitized))
        {
            flags.Add("phone_detected");
            sanitized = PhoneRegex.Replace(sanitized, "[PHONE_REDACTED]");
        }

        if (SsnRegex.IsMatch(sanitized))
        {
            flags.Add("ssn_detected");
            sanitized = SsnRegex.Replace(sanitized, "[SSN_REDACTED]");
        }

        if (CreditCardRegex.IsMatch(sanitized))
        {
            flags.Add("credit_card_detected");
            sanitized = CreditCardRegex.Replace(sanitized, "[CARD_REDACTED]");
        }

        return (sanitized, flags);
    }

    public static bool HasExternalEmail(string email)
    {
        if (string.IsNullOrEmpty(email)) return false;
        
        var internalDomains = new[] { "company.com", "internal.local" };
        return !internalDomains.Any(domain => email.EndsWith($"@{domain}", StringComparison.OrdinalIgnoreCase));
    }
}
