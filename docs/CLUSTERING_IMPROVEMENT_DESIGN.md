# Clustering Algorithm Improvement Design Document

**Created**: 2026-01-11  
**Branch**: `feature/improve-clustering-algorithm`  
**Author**: AI Assistant + Chen Zeming  
**Status**: ✅ Completed

---

## 1. Background & Problem Statement

### 1.1 Issue Discovery

During analysis of **Run ID #35** (CTS 15_r6 on Trimble T70), the following classification issues were identified:

| Issue | Severity | Description |
|-------|----------|-------------|
| Catch-all Cluster | 🔴 High | Cluster #22 contains 26 unrelated failures from different domains (Input, NFC, View) |
| Domain Fragmentation | 🟡 Medium | NFC tests split across 3 different clusters |
| Generic Assertion Grouping | 🔴 High | Tests with `java.lang.AssertionError` without detailed messages are incorrectly grouped |

### 1.2 Root Cause

The current clustering algorithm uses **only stack trace text** for TF-IDF vectorization. When failures have:
- Generic `AssertionError` without specific messages
- Common JUnit framework stack frames (`org.junit.Assert.fail`, `assertTrue`)

These dominate the TF-IDF features, causing unrelated failures to cluster together.

---

## 2. Original Architecture (Before)

### 2.1 Analysis Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ORIGINAL FLOW                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. Upload XML                                                       │
│       ↓                                                              │
│  2. Parse & Store TestCases (status=fail only)                       │
│       ↓                                                              │
│  3. Trigger Analysis (/analysis/run/{id})                            │
│       ↓                                                              │
│  4. Extract failure_texts = [stack_trace | error_message]            │
│       ↓                                                              │
│  5. FailureClusterer.cluster_failures(failure_texts)                 │
│       │                                                              │
│       │  ┌─────────────────────────────────────────┐                 │
│       │  │ TfidfVectorizer(max_features=1000)      │                 │
│       │  │ MiniBatchKMeans(n_clusters=dynamic)     │                 │
│       │  └─────────────────────────────────────────┘                 │
│       ↓                                                              │
│  6. Group failures by cluster label                                  │
│       ↓                                                              │
│  7. For each cluster: LLM analysis                                   │
│       ↓                                                              │
│  8. Link all failures to their clusters                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Original Code

```python
class FailureClusterer:
    def __init__(self, n_clusters=10):
        self.n_clusters = n_clusters
        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        self.kmeans = MiniBatchKMeans(n_clusters=n_clusters, random_state=42)

    def cluster_failures(self, failures: List[str]) -> List[int]:
        tfidf_matrix = self.vectorizer.fit_transform(failures)
        self.kmeans.fit(tfidf_matrix)
        return self.kmeans.labels_.tolist()
```

**Key Limitations**:

| Limitation | Impact |
|------------|--------|
| Input is pure stack trace text | No domain context (module, class) |
| Fixed K-Means | Forces k clusters regardless of data |
| No cluster quality metrics | Can't detect poor clustering |
| TF-IDF on raw traces | JUnit frames dominate features |

---

## 3. Implemented Solution

### 3.1 Strategy: Enriched Features + HDBSCAN + Hierarchical Fallback

```
┌─────────────────────────────────────────────────────────────────────┐
│                      IMPROVED FLOW                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Phase 1: Feature Engineering                                        │
│  ───────────────────────────                                         │
│  For each failure, create enriched text:                             │
│                                                                      │
│    enriched_text = f"{module_name} {module_name} {module_name} "     │
│                    f"{class_name} {class_name} {method_name} "       │
│                    f"{exception_type} {exception_type} "             │
│                    f"{assertion_msg} {filtered_stack}"               │
│                                                                      │
│  Key features:                                                       │
│    - Module name weighted 3x (most important for domain)             │
│    - Class name weighted 2x                                          │
│    - Exception type weighted 2x                                      │
│    - JUnit framework frames filtered out                             │
│                                                                      │
│  Phase 2: Clustering with HDBSCAN                                    │
│  ────────────────────────────────                                    │
│                                                                      │
│    ┌─────────────────────────────────────────┐                       │
│    │ TfidfVectorizer(max_features=2000,      │                       │
│    │                 ngram_range=(1,2))      │                       │
│    │ HDBSCAN(min_cluster_size=2)             │                       │
│    │ → Automatic cluster count               │                       │
│    │ → Outlier detection (label=-1)          │                       │
│    │ → Silhouette score for quality          │                       │
│    └─────────────────────────────────────────┘                       │
│                                                                      │
│  Phase 3: Hierarchical Fallback for Outliers                         │
│  ────────────────────────────────────────────                        │
│  Failures with label=-1 are grouped by module_name                   │
│  This ensures no failure is left ungrouped                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Key Implementation Details

See `backend/analysis/clustering.py` for full implementation.

Key methods:
- `extract_exception_type()` - Parse exception from stack trace
- `filter_framework_frames()` - Remove generic JUnit frames
- `extract_test_package()` - Get domain from class name
- `create_enriched_features()` - Build weighted feature text
- `cluster_failures()` - HDBSCAN with metrics
- `handle_outliers()` - Module-based fallback grouping
- `get_cluster_summary()` - Generate cluster statistics

### 3.3 Dependencies Added

```txt
# requirements.txt
hdbscan>=0.8.33
```

---

## 4. Validation Results

### 4.1 Test Suite

**18 unit tests created and passing:**

| Category | Tests |
|----------|-------|
| Exception extraction | 5 |
| Framework filtering | 2 |
| Enriched features | 3 |
| Clustering | 3 |
| Outlier handling | 2 |
| Legacy interface | 2 |
| Cluster summary | 1 |

### 4.2 Run #35 Comparison

| Metric | Original | Improved | Change |
|--------|----------|----------|--------|
| **Weighted Avg Purity** | 0.900 | **1.000** | +10% ✅ |
| **Number of Clusters** | 16 | 31 | More granular |
| **Silhouette Score** | N/A | **0.767** | High quality |
| **Clusters with purity < 0.8** | 2 | **0** | ✅ Perfect |
| **Outliers** | N/A | 2 | Handled |

### 4.3 Catch-All Cluster #22 Resolution

**Before**: Cluster #22 contained **26 failures** from:
- CtsInputTestCases
- CtsNfcTestCases
- CtsViewTestCases
- CtsAccessibilityTestCases

**After**: Split into **13 pure clusters** with purity = 1.00 for each.

### 4.4 Complete Cluster Distribution

All 31 clusters have **purity = 1.00**:

```
✅ Cluster #0: 2 failures, modules=['MctsMediaDrmFrameworkTestCases']
✅ Cluster #1: 2 failures, modules=['MctsMediaDrmFrameworkTestCases']
✅ Cluster #2: 5 failures, modules=['CtsPermissionTestCases']
✅ Cluster #3: 3 failures, modules=['CtsPermissionTestCases']
✅ Cluster #4: 5 failures, modules=['CtsPermissionMultiDeviceTestCases']
✅ Cluster #5: 2 failures, modules=['CtsPermissionMultiDeviceTestCases']
✅ Cluster #6: 8 failures, modules=['CtsViewTestCases']
✅ Cluster #7: 3 failures, modules=['CtsWindowManagerDeviceInput']
✅ Cluster #8: 3 failures, modules=['CtsWindowManagerDeviceMultiDisplay']
✅ Cluster #9: 2 failures, modules=['CtsNfcTestCases']
✅ Cluster #10: 3 failures, modules=['CtsNfcTestCases']
... (all 31 clusters at 100% purity)
```

---

## 5. Files Changed

| File | Change |
|------|--------|
| `backend/analysis/clustering.py` | Complete rewrite with `ImprovedFailureClusterer` |
| `backend/routers/analysis.py` | Updated to use new clustering interface |
| `requirements.txt` | Added `hdbscan` |
| `tests/test_clustering.py` | New: 18 unit tests |
| `validate_clustering_improvement.py` | New: Validation script |
| `docs/CLUSTERING_IMPROVEMENT_DESIGN.md` | This document |

---

## 6. Backward Compatibility

The original `FailureClusterer` class is preserved as a wrapper:

```python
class FailureClusterer(ImprovedFailureClusterer):
    """Legacy compatibility wrapper."""
    
    def cluster_failures(self, failures: List[str]) -> List[int]:
        # Converts string list to dict format
        # Infers module/class from stack traces where possible
        ...
```

---

## 7. Completion Checklist

- [x] Document created
- [x] Implement `ImprovedFailureClusterer`
- [x] Update `analysis.py` router
- [x] Add HDBSCAN to requirements
- [x] Write unit tests (18 tests passing)
- [x] Run validation on Run #35
- [x] Verify 100% purity on all clusters
- [x] Commit to feature branch

---

## 8. Future Improvements (Optional)

1. **Cluster Merging**: Optionally merge very small clusters from same module
2. **Semantic Embeddings**: Use LLM embeddings for better similarity
3. **Incremental Clustering**: Support adding new failures to existing clusters
4. **UI Visualization**: Add cluster quality metrics to frontend dashboard
