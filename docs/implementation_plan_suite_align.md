# Implementation Plan - Align Suite Logic with Failure Matrix

The user has identified that the "Failure Matrix" (Compliance Matrix) logic for categorizing "CTS" vs "CTSonGSI" is correct, while the new AI Analysis tabs are inconsistent.

## Problem
The "Compliance Matrix" logic in `backend/routers/submissions.py` uses a specific set of rules involving `device_fingerprint` comparison to identify GSI runs. The new `detectAvailableSuites` (frontend) and `get_submission_clusters` (backend) implementations logic is incomplete, missing the fingerprint check.

## Correct Logic (Source of Truth)
From `backend/routers/submissions.py`:
- **GSI Run**: Name contains 'CTS' AND (`device_fingerprint != target_fingerprint` OR `build_product/model` contains 'gsi').
- **CTS Run**: Name contains 'CTS' AND NOT (GSI Run).

## Proposed Changes

### 1. Frontend (`backend/static/app.js`)
Update `detectAvailableSuites(sub)` to implement the full logic:
- Check if `sub.target_fingerprint` is available.
- For each run, check `r.device_fingerprint` against `sub.target_fingerprint`.
- Update the condition for `CTSonGSI` to include the fingerprint mismatch.

### 2. Backend (`backend/routers/analysis.py`)
Update `get_submission_clusters`:
- Ensure `suite_filter` processing strictly follows the `match_suite` logic.
- Specifically, for `filter_upper == 'CTSONGSI'` (or 'GSI'), use the full GSI check.
- For `filter_upper == 'CTS'`, exclude runs matching the GSI check.

## Verification Plan

### Manual Verification
1.  **Load a Submission**: Use a submission that has both persistent CTS runs and GSI runs.
2.  **Check Tabs**: Verify `CTSonGSI` tab appears in the AI Analysis section.
3.  **Check Contents**:
    - Click `CTS` tab: Should show clusters for standard CTS runs.
    - Click `CTSonGSI` tab: Should show clusters for GSI runs.
    - Verify against "Compliance Matrix" counts.

### Automated Test (Browser)
- Use `browser_subagent` to navigate to the submission and confirm the correct tabs are present, effectively repeating the previous successful test but with stricter criteria.
