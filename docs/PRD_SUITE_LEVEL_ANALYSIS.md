
# PRD: Suite-Level AI Analysis & Triage Integration (Phase 5)

## 1. Problem Statement
Currently, the **Submission Details** page aggregates AI analysis (clustering, root cause analysis) across **all test runs** within a submission. This creates friction for users who need to:
1.  **Analyze specific suites** independently (e.g., "Show me only CTS failures").
2.  **Sync issues to Redmine** with suite-specific context (e.g., sync all "CTS" issues to the "Android T" project, but "GTS" issues to "GMS" project).
3.  **Perform LLM Analysis** on a per-suite basis to get more focused insights.

Users currently have to navigate back to individual "Test Run" pages to get this granularity, which is inefficient.

## 2. Goals
- **Granular Visibility**: Allow users to filter clusters and AI insights by Test Suite (CTS, GTS, VTS, STS) directly within the Submission Details page.
- **Scoped Actionability**: Enable "Sync All" actions that apply ONLY to the currently selected suite.
- **Context Preservation**: Maintain the "Submission" context while providing "Run-level" precision.

## 3. Functional Requirements

### 3.1 Suite Tabs in Analysis View
- **Location**: In the "AI Analysis" section of the Submission Details page.
- **Tabs**: Dynamically generated based on the runs present in the submission.
    - `All` (Default, existing aggregated view)
    - `CTS`
    - `GTS`
    - `VTS`
    - `STS`
    - `TGS` (or other detected suites)
- **Behavior**: Clicking a tab filters the **Clusters List**, **AI Summary**, and **KPI Cards** to show data only from runs belonging to that suite.

### 3.2 Scoped Cluster Filtering
- **Backend Filter**: The `GET /analysis/submission/{id}/clusters` endpoint must accept a `?suite=` parameter.
- **Computation**:
    - If `suite` is query param provided, filter the clusters to only those containing failures from TestRuns matching that suite name.
    - Re-calculate KPIs (Severity distribution, Top Category) based on the filtered failures.

### 3.3 Scoped LLM Analysis
- **Trigger**: "Run AI Analysis" button should respect the selected tab.
- **Optimization**:
    - If `All` is selected: Analyze global top patterns.
    - If `CTS` is selected: Analyze top patterns specific to CTS runs.
    - *(Note: This may require backend logic to segment analysis context by suite).*

### 3.4 Scoped Redmine Sync ("Sync All")
- **Action**: "Create Issues for All Clusters" button.
- **Logic**:
    - **Current**: Syncs all unlinked clusters in the submission.
    - **New**: Syncs all unlinked clusters **visible in the current tab**.
- **User Flow**:
    1. User selects "CTS" tab.
    2. User clicks "Helper: Sync All CTS Clusters".
    3. Modal confirms: "Create X issues for CTS suite?".
    4. Issues are created.
    5. User switches to "GTS" tab, repeats process (potentially targeting a different Redmine project).

## 4. Technical Architecture

### 4.1 UI Component Structure
```html
<!-- AI Analysis Section -->
<div id="submission-ai-analysis">
    <!-- Tabs -->
    <div class="segmented-control">
        <button class="active">All</button>
        <button>CTS</button>
        <button>GTS</button>
        <!-- ... -->
    </div>

    <!-- Toolbar -->
    <div class="flex justify-between">
        <button id="btn-analyze">Run AI Analysis (CTS)</button>
        <button id="btn-sync-filtered">Sync All CTS Issues</button>
    </div>

    <!-- Content -->
    <div id="analysis-clusters-list">
        <!-- Filtered Clusters -->
    </div>
</div>
```

### 4.2 API Extensions
1.  **Cluster List**:
    `GET /analysis/submission/{id}/clusters`
    - Add param `suite_filter: Optional[str]`.
    - Logic: Join `TestCase` -> `TestRun`. Filter `TestRun.test_suite_name` (fuzzy match or categorized).

2.  **Bulk Sync**:
    `POST /integrations/redmine/bulk-create`
    - Add param `suite_filter: Optional[str]`.
    - Logic: Use same filtering logic as above before iterating clusters to sync.

3.  **LLM Analysis** (Optional Phase 2):
    `POST /analysis/submission/{id}/analyze`
    - Add param `suite_filter: Optional[str]`.
    - Logic: Limit the context generation to failures from specific suites.

## 5. Implementation Roadmap
1.  **Backend**: Update `analysis.py` router to support `suite_filter` in cluster retrieval and bulk sync endpoints.
2.  **Frontend**: Refactor `renderSubmissionAnalysis` to support tabbed state.
3.  **Frontend**: Implement `detectAvailableSuites(submission)` to render tabs dynamically.
4.  **Integration**: Wire up the "Sync All" button to pass the current active filter to the backend.

## 6. Success Metrics
- Users can view and sync CTS and GTS issues separately without leaving the page.
- "Sync All" actions result in correct project mapping (e.g. user manually selects Project A for CTS sync, then Project B for GTS sync).
