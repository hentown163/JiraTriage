using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Azure.Identity;
using Azure.Security.KeyVault.Secrets;
using Microsoft.Extensions.Logging;
using Polly;
using Polly.Retry;

namespace JiraTriage.Core.Services;

public class JiraClientService
{
    private readonly HttpClient _httpClient;
    private readonly string _jiraBaseUrl;
    private readonly string _apiToken;
    private readonly string _userEmail;
    private readonly ILogger<JiraClientService>? _logger;
    private readonly AsyncRetryPolicy<HttpResponseMessage> _retryPolicy;

    public JiraClientService(
        HttpClient httpClient,
        string jiraBaseUrl,
        string apiToken,
        string userEmail,
        ILogger<JiraClientService>? logger = null)
    {
        _httpClient = httpClient;
        _jiraBaseUrl = jiraBaseUrl.TrimEnd('/');
        _apiToken = apiToken;
        _userEmail = userEmail;
        _logger = logger;
        
        var authToken = Convert.ToBase64String(Encoding.UTF8.GetBytes($"{_userEmail}:{_apiToken}"));
        _httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Basic", authToken);
        _httpClient.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
        
        _retryPolicy = Policy
            .HandleResult<HttpResponseMessage>(r =>
                r.StatusCode == HttpStatusCode.TooManyRequests ||
                r.StatusCode == HttpStatusCode.RequestTimeout ||
                r.StatusCode == HttpStatusCode.ServiceUnavailable ||
                r.StatusCode == HttpStatusCode.GatewayTimeout)
            .WaitAndRetryAsync(
                retryCount: 3,
                sleepDurationProvider: retryAttempt =>
                {
                    var delay = retryAttempt switch
                    {
                        1 => TimeSpan.FromSeconds(1),
                        2 => TimeSpan.FromSeconds(2),
                        _ => TimeSpan.FromSeconds(5)
                    };
                    
                    _logger?.LogWarning("Retry attempt {RetryAttempt} after {Delay}ms", retryAttempt, delay.TotalMilliseconds);
                    return delay;
                },
                onRetry: (outcome, timespan, retryCount, context) =>
                {
                    _logger?.LogWarning(
                        "Transient failure on attempt {RetryCount}. Status: {StatusCode}. Waiting {Delay}ms before retry.",
                        retryCount,
                        outcome.Result?.StatusCode,
                        timespan.TotalMilliseconds);
                });
    }

    public static async Task<JiraClientService> CreateFromKeyVaultAsync(
        HttpClient httpClient,
        string keyVaultUrl,
        string jiraBaseUrl,
        ILogger<JiraClientService>? logger = null)
    {
        var credential = new DefaultAzureCredential();
        var secretClient = new SecretClient(new Uri(keyVaultUrl), credential);
        
        logger?.LogInformation("Loading JIRA credentials from Key Vault: {KeyVaultUrl}", keyVaultUrl);
        
        var apiTokenSecret = await secretClient.GetSecretAsync("JIRA-API-TOKEN");
        var userEmailSecret = await secretClient.GetSecretAsync("JIRA-USER-EMAIL");
        
        logger?.LogInformation("Successfully loaded JIRA credentials for user: {UserEmail}", userEmailSecret.Value.Value);
        
        return new JiraClientService(
            httpClient,
            jiraBaseUrl,
            apiTokenSecret.Value.Value,
            userEmailSecret.Value.Value,
            logger
        );
    }

    public async Task<JiraIssue?> GetIssueAsync(string issueKey, CancellationToken cancellationToken = default)
    {
        try
        {
            _logger?.LogInformation("Fetching JIRA issue: {IssueKey}", issueKey);
            
            var url = $"{_jiraBaseUrl}/rest/api/3/issue/{issueKey}";
            var response = await _retryPolicy.ExecuteAsync(() => _httpClient.GetAsync(url, cancellationToken));
            
            if (!response.IsSuccessStatusCode)
            {
                _logger?.LogError("Failed to fetch issue {IssueKey}. Status: {StatusCode}", issueKey, response.StatusCode);
                return null;
            }
            
            var content = await response.Content.ReadAsStringAsync(cancellationToken);
            var issue = JsonSerializer.Deserialize<JiraIssue>(content, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });
            
            _logger?.LogInformation("Successfully fetched issue {IssueKey}", issueKey);
            return issue;
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Error fetching issue {IssueKey}", issueKey);
            return null;
        }
    }

    public async Task<bool> UpdateIssueAsync(
        string issueKey,
        string? assignee = null,
        string? priority = null,
        Dictionary<string, object>? customFields = null,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var updatePayload = new Dictionary<string, object>();
            var fields = new Dictionary<string, object>();

            if (!string.IsNullOrEmpty(assignee))
            {
                fields["assignee"] = new { accountId = assignee };
            }

            if (!string.IsNullOrEmpty(priority))
            {
                fields["priority"] = new { name = priority };
            }

            if (customFields != null)
            {
                foreach (var field in customFields)
                {
                    fields[field.Key] = field.Value;
                }
            }

            updatePayload["fields"] = fields;

            _logger?.LogInformation("Updating issue {IssueKey} with assignee={Assignee}, priority={Priority}", issueKey, assignee, priority);
            
            var url = $"{_jiraBaseUrl}/rest/api/3/issue/{issueKey}";
            var json = JsonSerializer.Serialize(updatePayload);
            var content = new StringContent(json, Encoding.UTF8, "application/json");
            
            var response = await _retryPolicy.ExecuteAsync(() => _httpClient.PutAsync(url, content, cancellationToken));
            
            if (response.IsSuccessStatusCode)
            {
                _logger?.LogInformation("Successfully updated issue {IssueKey}", issueKey);
                return true;
            }
            
            var errorContent = await response.Content.ReadAsStringAsync(cancellationToken);
            _logger?.LogError("Failed to update issue {IssueKey}. Status: {StatusCode}, Error: {Error}", issueKey, response.StatusCode, errorContent);
            return false;
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Error updating issue {IssueKey}", issueKey);
            return false;
        }
    }

    public async Task<bool> AddCommentAsync(
        string issueKey,
        string commentText,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var commentPayload = new
            {
                body = new
                {
                    type = "doc",
                    version = 1,
                    content = new[]
                    {
                        new
                        {
                            type = "paragraph",
                            content = new[]
                            {
                                new
                                {
                                    type = "text",
                                    text = commentText
                                }
                            }
                        }
                    }
                }
            };

            _logger?.LogInformation("Adding comment to issue {IssueKey}", issueKey);
            
            var url = $"{_jiraBaseUrl}/rest/api/3/issue/{issueKey}/comment";
            var json = JsonSerializer.Serialize(commentPayload);
            var content = new StringContent(json, Encoding.UTF8, "application/json");
            
            var response = await _retryPolicy.ExecuteAsync(() => _httpClient.PostAsync(url, content, cancellationToken));
            
            if (response.IsSuccessStatusCode)
            {
                _logger?.LogInformation("Successfully added comment to issue {IssueKey}", issueKey);
                return true;
            }
            
            var errorContent = await response.Content.ReadAsStringAsync(cancellationToken);
            _logger?.LogError("Failed to add comment to issue {IssueKey}. Status: {StatusCode}, Error: {Error}", issueKey, response.StatusCode, errorContent);
            return false;
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Error adding comment to issue {IssueKey}", issueKey);
            return false;
        }
    }

    public async Task<bool> AssignAndCommentAsync(
        string issueKey,
        string assignee,
        string priority,
        string comment,
        Dictionary<string, object>? customFields = null,
        CancellationToken cancellationToken = default)
    {
        var updateSuccess = await UpdateIssueAsync(issueKey, assignee, priority, customFields, cancellationToken);
        
        if (!updateSuccess)
        {
            return false;
        }

        var commentSuccess = await AddCommentAsync(issueKey, comment, cancellationToken);
        return commentSuccess;
    }
}

public class JiraIssue
{
    public string? Id { get; set; }
    public string? Key { get; set; }
    public JiraIssueFields? Fields { get; set; }
}

public class JiraIssueFields
{
    public string? Summary { get; set; }
    public string? Description { get; set; }
    public JiraIssueType? IssueType { get; set; }
    public JiraPriority? Priority { get; set; }
    public JiraUser? Reporter { get; set; }
    public JiraUser? Assignee { get; set; }
    public DateTime? Created { get; set; }
    public DateTime? Updated { get; set; }
    public JiraProject? Project { get; set; }
    public Dictionary<string, object>? CustomFields { get; set; }
}

public class JiraIssueType
{
    public string? Id { get; set; }
    public string? Name { get; set; }
}

public class JiraPriority
{
    public string? Id { get; set; }
    public string? Name { get; set; }
}

public class JiraUser
{
    public string? AccountId { get; set; }
    public string? DisplayName { get; set; }
    public string? EmailAddress { get; set; }
}

public class JiraProject
{
    public string? Id { get; set; }
    public string? Key { get; set; }
    public string? Name { get; set; }
}
