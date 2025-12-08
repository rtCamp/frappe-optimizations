## Sales Update Frequency Configuration

**Setting:** Selling Settings -> Sales Update Frequency in Company and Project -> Monthly

**Purpose:** This setting is required to avoid deadlock issues during Sales Invoice submission.

**Details:**
- By setting the update frequency to "Monthly" instead of real-time updates, we reduce the frequency of updates to Company and Project documents
- This prevents concurrent write operations that can cause deadlocks when multiple Sales Invoices are being submitted simultaneously
- The monthly update batches the sales updates, significantly reducing database lock contention
