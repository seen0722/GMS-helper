# Clustering Algorithm Improvement Design Document

**Created**: 2026-01-11  
**Branch**: `feature/improve-clustering-algorithm`  
**Author**: AI Assistant + Chen Zeming  
**Status**: In Progress

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

## 2. Current Architecture

### 2.1 Analysis Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CURRENT FLOW                                  │
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
│  7. For each cluster:                                                │
│       - Take first failure as representative                         │
│       - Call LLM with full context (module, class, method, stack)    │
│       - Store analysis in FailureCluster table                       │
│       ↓                                                              │
│  8. Link all failures to their clusters (FailureAnalysis table)      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Current Code

#### `backend/analysis/clustering.py`

```python
class FailureClusterer:
    def __init__(self, n_clusters=10):
        self.n_clusters = n_clusters
        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        self.kmeans = MiniBatchKMeans(n_clusters=n_clusters, random_state=42, batch_size=100)

    def cluster_failures(self, failures: List[str]) -> List[int]:
        # Dynamic cluster count adjustment
        n_samples = len(failures)
        if n_samples < self.n_clusters:
            self.kmeans.n_clusters = max(1, n_samples // 2)
            
        tfidf_matrix = self.vectorizer.fit_transform(failures)
        self.kmeans.fit(tfidf_matrix)
        return self.kmeans.labels_.tolist()
```

**Key Limitations**:

| Limitation | Impact |
|------------|--------|
| Input is pure stack trace text | No domain context (module, class) in clustering features |
| Fixed K-Means | Forces k clusters even when natural groupings differ |
| No cluster quality metrics | Can't detect poor clustering |
| TF-IDF on raw traces | JUnit framework frames dominate features |

#### `backend/analysis/llm_client.py`

```python
SYSTEM_PROMPT = """You are an expert Android GMS certification test engineer...

Return a JSON response with:
- 'title': Summary sentence (max 20 words)
- 'summary': Detailed technical summary
- 'root_cause': Why the test failed
- 'solution': Actionable steps to fix
- 'severity': High|Medium|Low
- 'category': Test Case Issue|Framework Issue|Media/Codec Issue|...
- 'confidence_score': 1-5
- 'suggested_assignment': Team name
"""

# Context sent to LLM (GOOD - has all info)
failure_context = f"""
Test Failure Details:
- Module: {module_name}
- Test Class: {class_name}
- Test Method: {method_name}
- Error Message: {error_message}
- Stack Trace: {stack_trace}
- Number of similar failures in cluster: {count}
"""
```

**LLM logic is correct** - it receives full context. The problem is **upstream clustering**.

### 2.3 Database Schema

```sql
-- Stores individual test failures
CREATE TABLE test_cases (
    id INTEGER PRIMARY KEY,
    test_run_id INTEGER,
    module_name VARCHAR,      -- e.g., CtsViewTestCases
    module_abi VARCHAR,
    class_name VARCHAR,       -- e.g., android.view.cts.TooltipTest
    method_name VARCHAR,      -- e.g., testLongKeyPressTooltip
    status VARCHAR,
    stack_trace TEXT,
    error_message TEXT
);

-- Stores cluster definitions with AI analysis
CREATE TABLE failure_clusters (
    id INTEGER PRIMARY KEY,
    signature TEXT UNIQUE,
    description VARCHAR,
    common_root_cause TEXT,
    common_solution TEXT,
    ai_summary TEXT,
    severity VARCHAR DEFAULT 'Medium',
    category VARCHAR,
    confidence_score INTEGER DEFAULT 0,
    suggested_assignment VARCHAR,
    redmine_issue_id INTEGER
);

-- Links failures to clusters
CREATE TABLE failure_analysis (
    id INTEGER PRIMARY KEY,
    test_case_id INTEGER,
    cluster_id INTEGER,
    root_cause TEXT,
    suggested_solution TEXT,
    ai_analysis_timestamp DATETIME
);
```

---

## 3. Proposed Improvement

### 3.1 Strategy: Enriched Features + HDBSCAN

We will implement a **two-phase approach**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      IMPROVED FLOW                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Phase 1: Feature Engineering                                        │
│  ───────────────────────────                                         │
│  For each failure, create enriched text:                             │
│                                                                      │
│    enriched_text = f"{module_name} {class_name} {method_name} "      │
│                    f"{extracted_exception} {key_stack_frames}"       │
│                                                                      │
│  Where:                                                              │
│    - extracted_exception = parse exception type from stack trace     │
│    - key_stack_frames = filter out generic JUnit frames              │
│                                                                      │
│  Phase 2: Clustering with HDBSCAN                                    │
│  ────────────────────────────────                                    │
│                                                                      │
│    ┌─────────────────────────────────────────┐                       │
│    │ TfidfVectorizer (enriched_text)         │                       │
│    │ HDBSCAN(min_cluster_size=2)             │                       │
│    │ → Automatic cluster count               │                       │
│    │ → Outlier detection (label=-1)          │                       │
│    └─────────────────────────────────────────┘                       │
│                                                                      │
│  Phase 3: Fallback for Outliers                                      │
│  ──────────────────────────────                                      │
│  Failures with label=-1 get individual LLM analysis                  │
│  OR grouped by module_name as secondary clustering                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Implementation Details

#### 3.2.1 New Clustering Class

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from typing import List, Dict, Tuple, Optional
import re

try:
    from hdbscan import HDBSCAN
    HDBSCAN_AVAILABLE = True
except ImportError:
    from sklearn.cluster import MiniBatchKMeans
    HDBSCAN_AVAILABLE = False


class ImprovedFailureClusterer:
    """
    Enhanced clustering with domain-aware feature engineering.
    
    Key improvements:
    1. Enriched features including module/class/method names
    2. Exception type extraction
    3. JUnit frame filtering
    4. HDBSCAN for automatic cluster count (with KMeans fallback)
    5. Cluster quality metrics
    """
    
    # JUnit/Android test framework frames to de-prioritize
    FRAMEWORK_PATTERNS = [
        r'org\.junit\.Assert\.',
        r'org\.junit\.internal\.',
        r'org\.junit\.runners\.',
        r'android\.test\.',
        r'androidx\.test\.',
        r'java\.lang\.reflect\.',
        r'sun\.reflect\.',
    ]
    
    def __init__(self, min_cluster_size: int = 2, use_hdbscan: bool = True):
        self.min_cluster_size = min_cluster_size
        self.use_hdbscan = use_hdbscan and HDBSCAN_AVAILABLE
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=2000,
            ngram_range=(1, 2)  # Include bigrams for better context
        )
        
    def extract_exception_type(self, stack_trace: str) -> str:
        """Extract the primary exception type from stack trace."""
        if not stack_trace:
            return ""
        
        # Match patterns like: java.lang.AssertionError, junit.framework.AssertionFailedError
        patterns = [
            r'^([a-z][a-z0-9_]*\.)+[A-Z][a-zA-Z0-9]*(?:Error|Exception)',
            r'Caused by: ([a-z][a-z0-9_]*\.)+[A-Z][a-zA-Z0-9]*(?:Error|Exception)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, stack_trace, re.MULTILINE)
            if match:
                return match.group(0).replace('Caused by: ', '')
        
        return ""
    
    def filter_framework_frames(self, stack_trace: str) -> str:
        """Remove generic framework frames to focus on application-specific traces."""
        if not stack_trace:
            return ""
        
        lines = stack_trace.split('\n')
        filtered = []
        
        for line in lines:
            is_framework = any(re.search(p, line) for p in self.FRAMEWORK_PATTERNS)
            if not is_framework:
                filtered.append(line)
        
        return '\n'.join(filtered)
    
    def create_enriched_features(
        self, 
        failures: List[Dict]
    ) -> List[str]:
        """
        Create enriched text features for clustering.
        
        Args:
            failures: List of dicts with keys:
                - module_name
                - class_name  
                - method_name
                - stack_trace
                - error_message
        
        Returns:
            List of enriched text strings for vectorization
        """
        enriched_texts = []
        
        for f in failures:
            module = f.get('module_name', '') or ''
            class_name = f.get('class_name', '') or ''
            method = f.get('method_name', '') or ''
            stack = f.get('stack_trace', '') or ''
            error = f.get('error_message', '') or ''
            
            # Extract key information
            exception_type = self.extract_exception_type(stack)
            filtered_stack = self.filter_framework_frames(stack)
            
            # Weight domain information by repetition
            enriched = f"""
            {module} {module} {module}
            {class_name} {class_name}
            {method}
            {exception_type} {exception_type}
            {error}
            {filtered_stack[:1000]}
            """
            
            enriched_texts.append(enriched.strip())
        
        return enriched_texts
    
    def cluster_failures(
        self, 
        failures: List[Dict]
    ) -> Tuple[List[int], Dict]:
        """
        Cluster failures using enriched features.
        
        Returns:
            Tuple of (labels, metrics)
            - labels: cluster assignments (-1 for outliers if using HDBSCAN)
            - metrics: dict with clustering quality info
        """
        if not failures:
            return [], {'n_clusters': 0}
        
        enriched_texts = self.create_enriched_features(failures)
        
        # Filter empty texts
        valid_mask = [bool(t.strip()) for t in enriched_texts]
        valid_texts = [t for t, v in zip(enriched_texts, valid_mask) if v]
        
        if not valid_texts:
            return [0] * len(failures), {'n_clusters': 1, 'method': 'fallback'}
        
        try:
            tfidf_matrix = self.vectorizer.fit_transform(valid_texts)
            
            if self.use_hdbscan:
                clusterer = HDBSCAN(
                    min_cluster_size=self.min_cluster_size,
                    min_samples=1,
                    metric='euclidean',
                    cluster_selection_method='eom'
                )
                labels = clusterer.fit_predict(tfidf_matrix.toarray())
                n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
                n_outliers = list(labels).count(-1)
                
                metrics = {
                    'method': 'hdbscan',
                    'n_clusters': n_clusters,
                    'n_outliers': n_outliers,
                    'outlier_ratio': n_outliers / len(labels) if labels.size else 0
                }
            else:
                # Fallback to KMeans
                n_clusters = min(20, max(1, len(valid_texts) // 3))
                kmeans = MiniBatchKMeans(n_clusters=n_clusters, random_state=42)
                labels = kmeans.fit_predict(tfidf_matrix)
                
                metrics = {
                    'method': 'kmeans',
                    'n_clusters': n_clusters,
                    'n_outliers': 0
                }
            
            # Map back to original indices
            full_labels = []
            valid_idx = 0
            for is_valid in valid_mask:
                if is_valid:
                    full_labels.append(int(labels[valid_idx]))
                    valid_idx += 1
                else:
                    full_labels.append(-1)  # Mark invalid as outlier
            
            return full_labels, metrics
            
        except Exception as e:
            print(f"Clustering failed: {e}")
            return [0] * len(failures), {'n_clusters': 1, 'method': 'error', 'error': str(e)}
    
    def handle_outliers(
        self, 
        failures: List[Dict], 
        labels: List[int]
    ) -> List[int]:
        """
        Handle outliers (label=-1) by grouping them by module_name.
        
        Returns updated labels with outliers assigned to new clusters.
        """
        if -1 not in labels:
            return labels
        
        max_label = max(l for l in labels if l >= 0) if any(l >= 0 for l in labels) else -1
        
        # Group outliers by module
        module_clusters = {}
        new_labels = labels.copy()
        
        for i, (label, failure) in enumerate(zip(labels, failures)):
            if label == -1:
                module = failure.get('module_name', 'Unknown')
                if module not in module_clusters:
                    max_label += 1
                    module_clusters[module] = max_label
                new_labels[i] = module_clusters[module]
        
        return new_labels
```

#### 3.2.2 Updated Analysis Router

Key changes to `backend/routers/analysis.py`:

```python
# Change from:
failure_texts = [f.stack_trace or f.error_message for f in failures]
clusterer = FailureClusterer(n_clusters=...)
labels = clusterer.cluster_failures(failure_texts)

# To:
failure_dicts = [
    {
        'module_name': f.module_name,
        'class_name': f.class_name,
        'method_name': f.method_name,
        'stack_trace': f.stack_trace,
        'error_message': f.error_message
    }
    for f in failures
]
clusterer = ImprovedFailureClusterer(min_cluster_size=2)
labels, metrics = clusterer.cluster_failures(failure_dicts)
labels = clusterer.handle_outliers(failure_dicts, labels)
```

### 3.3 Dependencies

```txt
# requirements.txt additions
hdbscan>=0.8.33
```

Note: HDBSCAN requires `numpy` and `scipy`. If installation fails, the system falls back to KMeans.

---

## 4. Expected Improvements

### 4.1 Quantitative Goals

| Metric | Current | Target |
|--------|---------|--------|
| Cluster Purity | ~60% | >85% |
| Cross-domain Mixing | High | Minimal |
| Outlier Handling | None | Module-based fallback |
| Feature Context | Stack trace only | Module + Class + Exception + Filtered stack |

### 4.2 Qualitative Improvements

1. **NFC tests** will cluster together (same module pattern)
2. **Input tests** will separate from View tests
3. **Media codec tests** will remain correctly grouped
4. **Permission tests** will cluster by permission type, not assertion type

---

## 5. Testing Plan

### 5.1 Unit Tests

```python
def test_extract_exception_type():
    clusterer = ImprovedFailureClusterer()
    
    # Test basic exception
    assert clusterer.extract_exception_type(
        "java.lang.AssertionError\n  at Test.method()"
    ) == "java.lang.AssertionError"
    
    # Test nested exception
    assert "NullPointerException" in clusterer.extract_exception_type(
        "Caused by: java.lang.NullPointerException"
    )

def test_enriched_features():
    clusterer = ImprovedFailureClusterer()
    failures = [
        {'module_name': 'CtsNfcTestCases', 'class_name': 'NfcAdapterTest', ...},
        {'module_name': 'CtsViewTestCases', 'class_name': 'TooltipTest', ...}
    ]
    
    texts = clusterer.create_enriched_features(failures)
    assert 'CtsNfcTestCases' in texts[0]
    assert 'CtsViewTestCases' in texts[1]
```

### 5.2 Integration Test

Re-run analysis on Run ID #35 and verify:
- Cluster #22 is split into separate domain clusters
- NFC tests are grouped together
- No cross-domain mixing

---

## 6. Migration Strategy

1. **Backward Compatibility**: New clustering produces same output format (list of labels)
2. **Feature Flag**: Can switch between old/new via config if needed
3. **Re-analysis**: Existing runs can be re-analyzed with new algorithm

---

## 7. Appendix: Run #35 Analysis Results

### Before (Current Algorithm)

| Cluster | Failures | Actual Domains | Issue |
|---------|----------|----------------|-------|
| #22 | 26 | Input + NFC + View + Accessibility | ❌ Mixed |
| #23 | 4 | NFC only | ✅ OK |
| #32 | 6 | WindowManager | ✅ OK |
| #35 | 4 | Media/Codec | ✅ OK |
| #40 | 8 | InputDevice | ✅ OK |

### Expected After (Improved Algorithm)

| Cluster | Failures | Expected Domain |
|---------|----------|-----------------|
| NEW-1 | ~8 | CtsInputTestCases |
| NEW-2 | ~4 | CtsNfcTestCases |
| NEW-3 | ~10 | CtsViewTestCases |
| NEW-4 | ~4 | CtsAccessibilityTestCases |
| #32 | 6 | WindowManager |
| #35 | 4 | Media/Codec |
| #40 | 8 | InputDevice |

---

**Next Steps**:
1. ✅ Document created
2. ⬜ Implement `ImprovedFailureClusterer`
3. ⬜ Update `analysis.py` router
4. ⬜ Add HDBSCAN to requirements
5. ⬜ Write unit tests
6. ⬜ Re-analyze Run #35 and validate
