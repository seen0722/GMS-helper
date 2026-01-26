# Task: Suite-Level AI Analysis & Triage Implementation

- [x] **Backend Implementation**
    - [x] Implement `GET /analysis/submission/{id}/clusters` endpoint in `backend/routers/analysis.py` <!-- id: 0 -->
    - [x] Update `backend/routers/integrations.py` to support `suite_filter` in bulk sync <!-- id: 1 -->
- [x] **Frontend Implementation**
    - [x] Refactor `loadSubmissionAnalysis` in `app.js` to fetch live data <!-- id: 2 -->
    - [x] Implement `detectAvailableSuites` helper function <!-- id: 3 -->
    - [x] Create Tab Component in `renderSubmissionAnalysis` <!-- id: 4 -->
    - [x] Implement "Sync All" with suite scope <!-- id: 5 -->
- [x] **Verification**
    - [x] Verify filtering logic works for CTS/GTS <!-- id: 6 -->
    - [x] Verify Redmine sync only targets visible clusters <!-- id: 7 -->
    - [x] Verify CTSonGSI tab appears correctly for GSI runs <!-- id: 8 -->

# Task: Analysis UI Unification (REQ-05 Search & Sort)
- [x] **Frontend Implementation**
    - [x] Add Search Input to Analysis Toolbar in `index.html`
    - [x] Implement `filterAnalysisTable` logic in `app.js`
    - [x] Make Table Headers sortable in `index.html`
    - [x] Implement `sortAnalysisTable` logic in `app.js`
