# CTS & GMS Certification Logic

This skill documents the business logic for GMS (Google Mobile Services) certification analysis used in this project. It covers Submission grouping, Test Suite classification, and Retry merging strategies.

## 1. Submission Concept (Grouping)
A **Submission** represents a certification attempt for a specific device build.
- **Key Identifier**: `Target Fingerprint` (The `device_fingerprint` of the *very first run* uploaded).
- **Scope**: All test runs linked to this Submission ID are considered part of the same certification effort.

## 2. Test Suite Classification
We automatically classify test runs into suites (CTS, CTSonGSI, VTS, GTS, STS) based on their metadata.

### Logic Rule
| Suite Name | Condition | Description |
| :--- | :--- | :--- |
| **CTS** | Name contains 'CTS' **AND** `run.fingerprint == submission.target_fingerprint` | Standard CTS run on the target build. |
| **CTSonGSI** | Name contains 'CTS' **AND** `run.fingerprint != submission.target_fingerprint` | CTS running on a Generic System Image (GSI). Fingerprint mismatch is the key indicator. |
| **VTS** | Name contains 'VTS' | Vendor Test Suite. |
| **GTS** | Name contains 'GTS' | Google Mobile Services Test Suite. |
| **STS** | Name contains 'STS' | Security Test Suite. |

> **Important**: The `CTSonGSI` classification is *implicit* based on the fingerprint difference. The raw XML usually just says "CTS".

## 3. Merge & Retry Logic (Consolidated Report)
When multiple runs exist for the same suite (e.g., Run #3, #7, #8 are all CTS), we merge them to calculate the "Effective" pass/fail status.

### Strategy: "Last Result Wins" (with Recovery Tracking)
For each unique test case (Module + Class + Method):
1.  **History**: Collect status from all runs in chronological order.
2.  **Initial Failure**: If the test failed in the *first* run of this suite.
3.  **Recovered**: If it failed initially but passed (or was missing/fixed) in the *latest* run.
4.  **Persistent**: If it failed in the *latest* run.

### Status Matrix
| Run 1 | Run 2 | Run 3 | Final Status | UI Label |
| :--- | :--- | :--- | :--- | :--- |
| <span style="color:red">Fail</span> | <span style="color:green">Pass</span> | - | **Pass** | <span style="color:green">Recovered</span> |
| <span style="color:red">Fail</span> | <span style="color:red">Fail</span> | <span style="color:green">Pass</span> | **Pass** | <span style="color:green">Recovered</span> |
| <span style="color:red">Fail</span> | <span style="color:red">Fail</span> | <span style="color:red">Fail</span> | **Fail** | <span style="color:red">Persistent</span> |
| <span style="color:green">Pass</span> | <span style="color:red">Fail</span> | <span style="color:red">Fail</span> | **Fail** | <span style="color:red">Regression</span> (Treated as Persistent) |

## 4. UI Implementation Details
- **Submission Card**:
    - Displays **Effective Failures** (Count of Persistent Failures).
    - If 0 Persistent but >0 Initial, displays "Recovered" in green.
    - If Name='CTS' but Fingerprint mismatch, explicit UI logic is needed to display it as 'CTSonGSI'.
- **Consolidated Report**:
    - Groups by Suite (Splitting CTS vs CTSonGSI).
    - Shows "Run History" sparkline (e.g., 🔴 -> 🔴 -> 🟢).
    - Filters: All / Persistent / Recovered.

## 5. Automation & AI
- **AI Analysis**: Should prioritize **Persistent** failures. Recovered failures are generally noise unless analyzing flakiness.
- **Cache Busting**: Frontend assets (`app.js`) use timestamp query params (`?v=...`) to ensure logic updates are immediately reflected.
