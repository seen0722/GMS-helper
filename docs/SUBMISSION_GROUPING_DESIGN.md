# Submission Grouping Design (v1.0)

**Date:** 2026-01-30
**Component:** `backend/services/submission_service.py`

## 1. Overview
The submission grouping logic is responsible for organizing test runs into logical "Submissions". A Submission represents a specific testing cycle or a software release milestone.

## 2. Grouping Rules

### 2.1 Exact Fingerprint Match (Standard)
For most test suites (GTS, STS, etc.), the system requires a **100% exact match** of the device fingerprint.
- **Fingerprint Format:** `Brand/Product/Device:Version/BuildID/Suffix`
- **Result:** Any variation in version or build ID will trigger the creation of a new submission.

### 2.2 System-Replace Match (GCTS / VTS)
For specific tests where the system image is replaced but the hardware/vendor layer remains consistent, we use a **Relaxed Grouping** logic.

#### Trigger Conditions:
- `suite_name == "CTS"` AND `suite_plan` contains `cts-on-gsi`
- **OR** `suite_name == "VTS"` AND `suite_plan` contains `vts`

#### Fingerprint Parsing Logic:
The fingerprint is parsed into four segments using Regex: `^([^:]+):([^/]+)/([^/]+)(/.+)$`

| Segment | Example | Matching Rule |
| :--- | :--- | :--- |
| **Prefix (Hardware)** | `Trimble/T70/thorpe` | **Must Match Exactly** |
| **Version** | `15` vs `11` | **Ignored** |
| **Build ID (System)** | `AQ3A.250408.001` | **Ignored** |
| **Suffix (Vendor)** | `/02.00.11.2508...` | **Must Match Exactly** |

## 3. Implementation Details
The logic is centralized in `SubmissionService.get_or_create_submission`. This ensures consistency across:
- **XML Upload** (`upload.py`)
- **JSON Import** (`import_json.py`)
- **Data Repair Scripts** (`regroup_runs.py`)

### Logic Pseudocode:
```python
if is_system_replace(run):
    prefix, suffix = parse_fingerprint(run.fp)
    match = find_submission(prefix=prefix, suffix=suffix)
    if match: return match
else:
    match = find_submission(full_fp=run.fp)
    if match: return match

# Formula: [Brand] [Model] ([Device]) - [Security Patch] (Build: [Suffix])
return create_new_submission(run.metadata)
```

## 4. Rationale
- **Vendor Integrity:** By requiring the Vendor Suffix (Group 4) to match, we ensure that test runs are only grouped together if they share the same underlying vendor software stack.
- **System Flexibility:** Ignoring Version and Build ID for GCTS/VTS allows teams to track the progress of a single hardware release across multiple System Image revisions.
