# JIRA Webhook Integration Guide

**For: JIRA Triage Agent Platform**  
**Last Updated:** October 20, 2025

---

## Overview

This guide will walk you through configuring JIRA to send webhook notifications to your JIRA Triage Agent system. When configured, JIRA will automatically notify your system whenever new tickets are created, allowing the AI to analyze and triage them.

---

## Prerequisites

Before you begin, ensure you have:

✅ **JIRA Administrator Permissions** - You need admin access to configure webhooks  
✅ **Your Server URL** - The public URL where your webhook receiver is hosted  
✅ **HTTPS Certificate** - JIRA Cloud requires HTTPS (HTTP works for JIRA Server/Data Center in dev)  
✅ **Webhook API Running** - The JiraTriage.Webhook service should be running on port 5001

---

## Step-by-Step Configuration

### Step 1: Get Your Webhook Endpoint URL

Your webhook endpoint will be:

```
https://your-domain.com/api/webhook
```

**For Local Testing:**
```
http://your-replit-url.repl.co/api/webhook
```

**Important Notes:**
- The endpoint expects POST requests
- JIRA Cloud requires HTTPS with a valid SSL certificate
- JIRA Server/Data Center can use HTTP for development

---

### Step 2: Access JIRA Webhook Settings

#### For JIRA Cloud:

1. Log in to JIRA as an administrator
2. Click the **Settings icon (⚙️)** in the top-right corner
3. Select **System**
4. In the left sidebar, under **Advanced**, click **WebHooks**

**Direct URL:** `https://your-jira-instance.atlassian.net/plugins/servlet/webhooks`

#### For JIRA Server/Data Center:

1. Log in to JIRA as an administrator
2. Click **Settings (⚙️)** → **System**
3. Under **Advanced**, select **WebHooks**

---

### Step 3: Create a New Webhook

1. Click the **Create a WebHook** button (top-right corner)

2. Fill in the webhook details:

   **Name:**
   ```
   JIRA Triage Agent - Auto Classification
   ```

   **Status:**
   - ✅ Enabled

   **URL:**
   ```
   https://your-domain.com/api/webhook
   ```
   Replace with your actual server URL

   **Description:** (Optional)
   ```
   Sends new ticket notifications to the AI-powered triage system for automatic classification and routing
   ```

---

### Step 4: Select Events to Monitor

For this system to work, you need to subscribe to the following events:

**Required Event:**
- ✅ **Issue → created**

**Optional Events** (for future enhancements):
- Issue → updated
- Issue → deleted
- Issue → assigned
- Issue → commented

**Recommendation:** Start with just "Issue created" to keep it simple.

---

### Step 5: Add JQL Filter (Optional but Recommended)

To only triage specific types of tickets, add a JQL (JIRA Query Language) filter:

**Example 1 - Specific Projects:**
```jql
project in (SUPPORT, HELPDESK, IT)
```

**Example 2 - Exclude Internal Tickets:**
```jql
project = SUPPORT AND reporter not in (employeeGroup)
```

**Example 3 - Only Bugs and Tasks:**
```jql
issueType in (Bug, Task, "Service Request")
```

**Leave Empty** if you want ALL new tickets to be processed.

---

### Step 6: Configure Security (Recommended)

#### Option A: Secret Token (Recommended)

1. In the webhook configuration, look for **Secret** or **Token** field
2. Generate a strong secret token (or use this example):
   ```
   your-secure-secret-token-here-12345
   ```
3. **Save this token** - you'll need to add it to your system's configuration

4. Update your `.env` file (create one if it doesn't exist):
   ```bash
   JIRA_WEBHOOK_SECRET=your-secure-secret-token-here-12345
   ```

#### Option B: IP Allowlist

Alternatively, configure your firewall to only accept webhook requests from JIRA's IP addresses.

**JIRA Cloud IP Ranges:** [Check Atlassian's official list](https://support.atlassian.com/organization-administration/docs/ip-addresses-and-domains-for-atlassian-cloud-products/)

---

### Step 7: Save and Activate

1. Review all your settings
2. Click **Create** button
3. You should see your new webhook in the list with status **Enabled**

---

## Testing Your Webhook

### Test Method 1: Create a Test Ticket in JIRA

1. Go to your JIRA project
2. Create a new issue:
   - **Summary:** "Test webhook integration - Database timeout"
   - **Description:** "Cannot connect to staging DB - timeout after 30s"
   - **Type:** Bug
   - **Priority:** High
3. Click **Create**
4. Check your system dashboard at `http://your-url:5000`

### Test Method 2: Manual Webhook Test (using curl)

```bash
curl -X POST http://localhost:5001/api/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "webhookEvent": "jira:issue_created",
    "timestamp": 1697000000,
    "issue": {
      "id": "10001",
      "key": "TEST-123",
      "fields": {
        "summary": "Database connection timeout",
        "description": "Cannot connect to staging DB - timeout after 30s",
        "issuetype": { "name": "Bug" },
        "priority": { "name": "High" },
        "reporter": {
          "accountId": "user123",
          "displayName": "John Doe",
          "emailAddress": "john@company.com"
        }
      }
    }
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Webhook received and queued for processing"
}
```

---

## Verifying Integration

### Check 1: JIRA Webhook Logs

1. Go back to **System → WebHooks**
2. Click on your webhook name
3. Scroll down to **Recent Deliveries** section
4. Look for:
   - ✅ Green checkmarks = Successful delivery (HTTP 200-299)
   - ❌ Red X = Failed delivery (check error message)

### Check 2: Your System Logs

1. Check the webhook service logs:
   ```bash
   cd src/ControlPlane/JiraTriage.Webhook
   dotnet run
   ```
2. Look for messages like:
   ```
   info: Received webhook event: jira:issue_created for ticket TEST-123
   ```

### Check 3: Dashboard

1. Open your dashboard: `http://your-url:5000`
2. Check "Pending Reviews" or "Auto-Processed Today" counts
3. Click "View All" to see processed tickets

---

## What Happens After Configuration?

```
1. User creates ticket in JIRA
   ↓
2. JIRA sends webhook POST to your /api/webhook endpoint
   ↓
3. Your .NET Webhook API receives it
   ↓
4. System sanitizes data (removes PII like emails, phone numbers)
   ↓
5. Python AI Agent classifies:
   - Department (IT Support, HR, Finance)
   - Team assignment
   - Priority level
   ↓
6. If confidence is HIGH (>70%):
   → Automatically updates JIRA ticket
   
7. If confidence is LOW (<70%):
   → Flags for human review in dashboard
```

---

## Troubleshooting

### Issue: "Webhook deliveries failing"

**Solution:**
- ✅ Verify your server URL is correct and accessible
- ✅ For JIRA Cloud, ensure you're using HTTPS
- ✅ Check firewall rules aren't blocking JIRA's IPs
- ✅ Verify the webhook endpoint is running (port 5001)

### Issue: "Getting 404 errors"

**Solution:**
- ✅ Verify the URL ends with `/api/webhook`
- ✅ Check that JiraTriage.Webhook service is running
- ✅ Review logs for routing errors

### Issue: "Webhooks received but not processing"

**Solution:**
- ✅ Check that the Worker service is running (JiraTriage.Worker)
- ✅ Verify Python agent is running on port 8001
- ✅ Check system logs for errors

### Issue: "JIRA says 'SSL certificate invalid'"

**Solution:**
- ✅ For production, get a valid SSL certificate (Let's Encrypt is free)
- ✅ For testing, use ngrok or similar tunneling service
- ✅ JIRA Server/Data Center can use HTTP for dev environments

---

## Security Best Practices

### 1. Always Use HTTPS in Production
Never expose webhook endpoints over plain HTTP in production.

### 2. Validate Webhook Signatures
The system should verify the secret token on each request.

### 3. Implement Rate Limiting
Protect against webhook spam or DoS attacks.

### 4. Log All Webhook Events
Keep an audit trail of all received webhooks.

### 5. Use IP Allowlisting
Only accept webhooks from known JIRA IP addresses.

---

## Advanced Configuration

### Multiple Webhooks for Different Events

You can create separate webhooks for different purposes:

1. **Webhook 1:** Issue Created → Auto-triage
2. **Webhook 2:** Issue Updated → Track changes
3. **Webhook 3:** Issue Commented → Sentiment analysis

### Filtering by Custom Fields

If you have custom fields in JIRA:

```jql
project = SUPPORT AND "Customer Type" = "Enterprise"
```

### Conditional Processing

You can configure the webhook to only fire when specific conditions are met:

```jql
priority in (High, Highest, Blocker)
```

---

## Production Deployment Checklist

Before going live, ensure:

- [ ] HTTPS certificate installed and valid
- [ ] Secret token configured and secured
- [ ] JQL filters tested and working
- [ ] All three services running (Webhook, Worker, UI)
- [ ] Python AI agent connected
- [ ] Error handling and logging in place
- [ ] Test webhook with real JIRA ticket
- [ ] Monitor webhook delivery success rate
- [ ] Set up alerts for webhook failures
- [ ] Document runbook for webhook issues

---

## Getting Help

### JIRA Webhook Issues
- [Atlassian Webhook Documentation](https://developer.atlassian.com/cloud/jira/platform/webhooks/)
- [JIRA Cloud Admin Support](https://support.atlassian.com/)

### System Issues
- Check logs in `/tmp/logs/` directory
- Review dashboard at port 5000
- Verify all services are running

---

## Next Steps

After successful webhook configuration:

1. ✅ Monitor the first few tickets to ensure proper classification
2. ✅ Review AI predictions in the dashboard
3. ✅ Fine-tune confidence thresholds if needed
4. ✅ Add more department verticals as needed
5. ✅ Set up alerting for failed webhook deliveries

---

**Congratulations!** 🎉 Your JIRA integration is now complete. New tickets will automatically flow into your AI-powered triage system.
