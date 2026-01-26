# Implementation Plan - Refine Suite Logic for CTSonGSI variants

The user has clarified that `CTS` and `CTSonGSI` both share `suite_name="CTS"`. The distinction is that `CTSonGSI` is a variant where the run is executed on a GSI build (fingerprint mismatch vs target), whereas standard `CTS` matches the target fingerprint.

**Goal**: Apply this classification logic consistently across all pages (Dashboard, Submission Details, AI Analysis) and fix bugs where this distinction was missing.

## Core Logic (Source of Truth)

| Category | `suite_name` | Logic |
| :--- | :--- | :--- |
| **CTS** | "CTS" | `device_fingerprint == target_fingerprint` AND `!product.contains("gsi")` |
| **CTSonGSI** | "CTS" | `device_fingerprint != target_fingerprint` OR `product.contains("gsi")` |
| **GTS** | "GTS" | `suite_name.contains("GTS")` |
| **VTS** | "VTS" | `suite_name.contains("VTS")` |

## Proposed Changes

### 1. Backend: `backend/routers/analysis.py`
- Update `get_submission_clusters`:
    - **Remove** reliance on `match_suite` logic that might be inconsistent.
    - **Implement** strict filtering:
        - If `suite_filter == 'CTS'`: Include runs where `suite_name == 'CTS'` AND `is_gsi == False`.
        - If `suite_filter == 'CTSonGSI'` (or 'GSI'): Include runs where `suite_name == 'CTS'` AND `is_gsi == True`.

### 2. Frontend: `backend/static/app.js`
- **`detectAvailableSuites(sub)`**:
    - Iterate through runs.
    - If `run.test_suite_name == 'CTS'`:
        - Check `run.device_fingerprint` vs `sub.target_fingerprint`.
        - If mismatch (or product has 'gsi'), add `CTSonGSI`.
        - Else, add `CTS`.
- **`renderSubmissionRuns`**:
    - Ensure headers ("CTS", "CTSonGSI") leverage the same classification logic to group runs correctly in the list view.

### 3. Backend: `backend/routers/submissions.py` (Dashboard & Details)
- Verify `match_suite` in `get_submissions` and `get_submission_details` aligns with this logic. (It seems close, but needs double-checking the "CTS" exclusion logic).
- Ensure `suite_summary` correctly buckets runs into "CTS" vs "CTSonGSI" based on this split.

## Verification Plan

### Manual Verification
1.  **Dashboard**: Check the "Compliance Matrix" tiles. Ensure "CTS" and "CTSonGSI" tiles are distinct and accurate.
2.  **Submission Details**:
    - **Run List**: Verify runs are grouped under correct headers ("CTS" vs "CTSonGSI").
    - **AI Analysis**: Verify tabs "CTS" and "CTSonGSI" appear and filter data correctly.
3.  **Data Validation**: Inspect a specific run known to be GSI (different fingerprint) and ensure it ONLY appears in CTSonGSI sections.
