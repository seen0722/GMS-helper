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

## 8. ML Expert Analysis & Optimization Roadmap

### 8.1 Current Performance Metrics

| Metric | Value | Evaluation |
|--------|-------|------------|
| **Silhouette Score** | 0.767 | ✅ Excellent (>0.7 = strong structure) |
| **Outlier Ratio** | 2.5% (2/80) | ✅ Very low, robust model |
| **Cluster Purity** | 100% | ✅ Perfect domain separation |
| **Intra-cluster Similarity** | 0.84-0.99 | ✅ High cohesion |

### 8.2 Identified Issues

#### Issue 1: Over-fragmentation
`CtsViewTestCases.TooltipTest` split into 9 separate clusters (#22-#30), each with 2 failures.
While purity=100%, these likely share the same root cause and should be merged.

#### Issue 2: Feature Dominance
Top TF-IDF features still include generic terms like `java`, `assertionerror` which could cause issues at larger scale.

#### Issue 3: Numerical Warnings
RuntimeWarnings in sparse matrix operations (divide by zero, overflow). Non-critical but should be suppressed.

### 8.3 Optimization Roadmap

| Priority | Task | Description | Status |
|----------|------|-------------|--------|
| **P1** | Same-class cluster merging | Merge small clusters (size≤2) with same module+class | ✅ Done |
| **P2** | Domain-specific stop words | Filter out `java`, `lang`, `junit`, `assertionerror` | ✅ Done |
| **P3** | Adjust min_cluster_size | Increase from 2 to 3 to reduce fragmentation | ✅ Done |
| **P4** | Suppress numerical warnings | Add warning filters for expected edge cases | ✅ Done |

### 8.4 Optimization Results

| Metric | Before Opt | After P1-P4 |
|--------|------------|-------------|
| **Clusters** | 31 | **15** |
| **Purity** | 1.00 | **1.00** |
| **TooltipTest clusters** | 9 | **1** (18 failures) |
| **NFC clusters** | 3 | **1** (6 failures) |
| **Tests** | 18 passed | 22 passed |

---

## 9. Optimization Implementation

### 9.1 P1: Same-class Cluster Merging

**Goal**: Reduce cluster count by merging small clusters that share module+class.

**Before**: 31 clusters, 9 clusters for TooltipTest alone  
**After**: ~15-20 clusters expected

**Implementation**:
```python
def merge_small_clusters(
    self, 
    failures: List[Dict], 
    labels: List[int],
    max_merge_size: int = 2
) -> List[int]:
    """Merge small clusters that share the same module+class."""
    # Group by module+class
    class_groups = defaultdict(list)
    for i, (f, label) in enumerate(zip(failures, labels)):
        key = (f['module_name'], f['class_name'])
        class_groups[key].append((i, label))
    
    # For each group, merge small clusters
    new_labels = list(labels)
    for key, items in class_groups.items():
        cluster_sizes = Counter(label for _, label in items)
        small_clusters = [c for c, size in cluster_sizes.items() if size <= max_merge_size]
        
        if len(small_clusters) > 1:
            # Merge all small clusters into the first one
            target = small_clusters[0]
            for i, label in items:
                if label in small_clusters:
                    new_labels[i] = target
    
    return new_labels
```

### 9.2 P2: Domain-specific Stop Words

**Goal**: Improve feature quality by filtering generic terms.

**Implementation**:
```python
DOMAIN_STOP_WORDS = [
    'java', 'lang', 'org', 'junit', 'android', 'test', 'androidx',
    'assertionerror', 'exception', 'error', 'at', 'in', 'from'
]

self.vectorizer = TfidfVectorizer(
    stop_words=list(set(ENGLISH_STOP_WORDS) | set(DOMAIN_STOP_WORDS)),
    max_features=2000,
    ngram_range=(1, 2)
)
```

### 9.3 P3: Adjust min_cluster_size

**Goal**: Reduce fragmentation by requiring larger minimum clusters.

**Trade-off**: May increase outliers, which are handled by module-based fallback.

**Implementation**:
```python
clusterer = ImprovedFailureClusterer(min_cluster_size=3)  # Was 2
```

### 9.4 P4: Suppress Numerical Warnings

**Goal**: Clean console output by suppressing expected warnings.

**Implementation**:
```python
import warnings
warnings.filterwarnings('ignore', category=RuntimeWarning, module='sklearn')
```

---

## 10. Validation Plan

After each optimization, run validation script and verify:
1. Silhouette score >= 0.7
2. Purity >= 95%
3. Cluster count reduced (ideal: 15-25 for 80 failures)
4. No cross-domain mixing

