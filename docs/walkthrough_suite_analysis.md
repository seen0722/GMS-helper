# Walkthrough: Suite-Level AI Analysis & Triage

I have implemented the **Suite-Level Analysis** features, allowing you to filter AI insights and perform bulk actions scoped to specific test suites (CTS, GTS, etc.) within a Submission.

## 1. Feature Overview

### Suite-Specific Tabs
In the **AI Analysis** section of the Submission Details page, you will now see tabs for each test suite detected in your submission (e.g., `All`, `CTS`, `GTS`, `VTS`).

### Scoped Filtering
Clicking a tab filters the **Failure Patterns (Clusters)** list to show only clusters relevant to that suite.
- **KPIs**: Severity scores and stats are re-calculated based on the filtered view.
- **Cluster Counts**: The "Occurrences" count for each cluster reflects only failures within the selected suite.

### Scoped "Sync All"
A new **"Sync All [Suite]"** button appears when viewing a specific suite.
- Clicking this will batch-create Redmine issues **only** for the unsynced clusters visible in the current tab.
- This allows you to sync CTS issues to one project and GTS issues to another without cross-contamination.

## 2. Technical Implementation

### Frontend (`app.js`)
- Refactored `loadSubmissionAnalysis` to accept a `suiteFilter` parameter.
- Implemented `detectAvailableSuites` to dynamically generate tabs based on uploaded runs.
- Updated `renderSubmissionAnalysis` to display tabs and the "Sync All" button.

### Backend (`analysis.py`)
- Added `GET /analysis/submission/{id}/clusters?suite_filter=...`.
- Implemented filtering logic to join `TestRun` -> `TestCase` -> `FailureAnalysis` and filter by suite name (standard CTS vs GSI logic applied).

### Backend (`integrations.py`)
- Added `POST /integrations/redmine/submission/bulk-create`.
- Accepts `submission_id` and `suite_filter`.
- Syncs only clusters linked to the filtered test runs.

## 3. Verification
1.  **Tab Generation**: Upload a submission with CTS and GTS logs. Verify both tabs appear.
2.  **Filtering**: Click "CTS". verify cluster counts match CTS failures.
3.  **Sync**: Click "Sync All CTS". Check Redmine to ensure only CTS tickets were created.
