# Implementation Plan - Suite-Level AI Analysis (Phase 5)

## User Review Required
> [!IMPORTANT]
> This plan introduces a new API endpoint `GET /analysis/submission/{id}/clusters`. The frontend `loadSubmissionAnalysis` logic will need to be refactored to fetch LIVE data from this endpoint instead of relying solely on the static `analysis_result` JSON blob stored in the `Submission` table. This is a significant architectural improvement that enables real-time filtering but requires careful refactoring.

## Proposed Changes

### Backend
#### [NEW] `backend/routers/analysis.py`
- Implement `GET /submission/{submission_id}/clusters`
    - Accepts `suite_filter` query parameter.
    - Joins `TestRun` -> `TestCase` -> `FailureAnalysis` -> `FailureCluster`.
    - Filters by `TestRun.test_suite_name` (fuzzy match similar to `match_suite` logic in `submissions.py`).
    - Returns list of clusters with aggregated stats (failure count within that suite scope).

#### [MODIFY] `backend/routers/integrations.py`
- Update `bulk_create` (or create new `bulk_create_submission`) to accept `suite_filter`.
- Logic:
    - If `suite_filter` is present, look up applicable `TestRun` IDs first.
    - Filter clusters that have failures *only* (or *at least*) in those runs?
    - **Logic Refinement**: A cluster is a grouping of failures. If we filter by suite, we want to sync clusters that have *failures in that suite*.
    - If a cluster spans multiple suites (e.g. same failure in CTS and GTS), and we filter "CTS", we sync it. The Redmine issue will link to that cluster.
    - *Edge Case*: If previously synced for GTS, and now we filter CTS, it's already synced. The UI handles this (it's already linked). The "Bulk Sync" only targets unlinked clusters.

### Frontend
#### [MODIFY] `backend/static/app.js`
- **Tab Component**:
    - Inject tabs into the AI Analysis section in `renderSubmissionAnalysis` (or `loadSubmissionAnalysis`).
    - Logic to detect available suites from `currentSubmissionDetails.test_runs`.
- **Data Fetching**:
    - `loadSubmissionAnalysis(subId, suiteFilter)` function updates.
    - Fetch from the new `GET /analysis/submission/{id}/clusters` endpoint.
- **Rendering**:
    - Update `renderSubmissionAnalysis` to accept the dynamic cluster list instead of the static report format.
    - *Compatibility*: The static report format `analyzed_clusters` vs the API cluster list format might differ. I should standardize on the API format which is richer (includes IDs, real-time sync status).

## Verification Plan

### Automated Tests
- None planned for this iteration (relying on manual verification).

### Manual Verification
1.  **Tab Rendering**: Verify tabs appear (CTS, GTS, etc.) based on uploaded runs.
2.  **Filtering**: Click "CTS" tab -> Verify cluster count matches CTS failures. Click "GTS" -> Verify count changes.
3.  **Sync**: Select "CTS" tab -> Click "Sync All" -> Verify Redmine issues created only for clusters visible in that tab.
4.  **Cross-Suite**: Verify a cluster that exists in both suites appears in both tabs.
