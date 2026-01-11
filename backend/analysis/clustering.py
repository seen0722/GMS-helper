"""
Improved Failure Clustering Module

This module implements an enhanced clustering algorithm for CTS/GMS test failures
using domain-aware feature engineering and HDBSCAN for automatic cluster discovery.

Key improvements over the original implementation:
1. Enriched features: module_name, class_name, method_name included in vectorization
2. Exception type extraction: Primary exception is weighted higher
3. Framework frame filtering: Generic JUnit frames are de-prioritized
4. HDBSCAN: Automatic cluster count with outlier detection
5. Hierarchical fallback: Outliers grouped by module_name

Author: Chen Zeming + AI Assistant
Date: 2026-01-11
"""

import warnings
# P4: Suppress numerical warnings from sparse matrix operations
warnings.filterwarnings('ignore', category=RuntimeWarning, module='sklearn')

from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics import silhouette_score
from typing import List, Dict, Tuple, Optional, Any
from collections import Counter, defaultdict
import re
import numpy as np

# Try to import HDBSCAN, fallback to KMeans if not available
try:
    from hdbscan import HDBSCAN
    HDBSCAN_AVAILABLE = True
except ImportError:
    HDBSCAN_AVAILABLE = False
    print("HDBSCAN not available, falling back to KMeans")

from sklearn.cluster import MiniBatchKMeans


class ImprovedFailureClusterer:
    """
    Enhanced clustering with domain-aware feature engineering.
    
    This clusterer addresses the "catch-all cluster" problem by:
    1. Weighting domain context (module/class) in feature vectors
    2. Using HDBSCAN for automatic cluster discovery
    3. Providing outlier handling via module-based grouping
    """
    
    # JUnit/Android test framework frames to de-prioritize
    FRAMEWORK_PATTERNS = [
        r'org\.junit\.Assert\.',
        r'org\.junit\.internal\.',
        r'org\.junit\.runners\.',
        r'org\.junit\.rules\.',
        r'android\.test\.',
        r'androidx\.test\.',
        r'java\.lang\.reflect\.',
        r'sun\.reflect\.',
        r'jdk\.internal\.reflect\.',
        r'dalvik\.system\.',
    ]
    
    # P2: Domain-specific stop words to filter out generic terms
    DOMAIN_STOP_WORDS = [
        'java', 'lang', 'org', 'junit', 'android', 'test', 'androidx',
        'assertionerror', 'exception', 'error', 'assert', 'at', 'in', 'from',
        'com', 'cts', 'null', 'true', 'false', 'expected', 'but', 'was',
    ]
    
    # Common Android exception types for extraction
    EXCEPTION_PATTERNS = [
        r'^([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*\.[A-Z][a-zA-Z0-9]*(?:Error|Exception|Failure))',
        r'Caused by:\s*([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*\.[A-Z][a-zA-Z0-9]*(?:Error|Exception|Failure))',
    ]
    
    def __init__(
        self, 
        min_cluster_size: int = 2, 
        use_hdbscan: bool = True,
        min_samples: int = 1,
        max_features: int = 2000
    ):
        """
        Initialize the improved clusterer.
        
        Args:
            min_cluster_size: Minimum number of samples for a cluster (HDBSCAN)
            use_hdbscan: Whether to use HDBSCAN (True) or KMeans fallback (False)
            min_samples: HDBSCAN min_samples parameter
            max_features: Maximum features for TF-IDF vectorizer
        """
        self.min_cluster_size = min_cluster_size
        self.use_hdbscan = use_hdbscan and HDBSCAN_AVAILABLE
        self.min_samples = min_samples
        # P2: Combine English stop words with domain-specific stop words
        combined_stop_words = list(set(ENGLISH_STOP_WORDS) | set(self.DOMAIN_STOP_WORDS))
        
        self.vectorizer = TfidfVectorizer(
            stop_words=combined_stop_words,
            max_features=max_features,
            ngram_range=(1, 2),  # Include bigrams for better context
            sublinear_tf=True,   # Apply sublinear tf scaling
            min_df=1,            # Include rare terms (important for specific errors)
        )
        self._last_metrics: Dict[str, Any] = {}
        
    def extract_exception_type(self, stack_trace: str) -> str:
        """
        Extract the primary exception type from stack trace.
        
        Args:
            stack_trace: Full stack trace text
            
        Returns:
            Exception class name (e.g., 'java.lang.AssertionError') or empty string
        """
        if not stack_trace:
            return ""
        
        for pattern in self.EXCEPTION_PATTERNS:
            match = re.search(pattern, stack_trace, re.MULTILINE)
            if match:
                return match.group(1)
        
        return ""
    
    def extract_assertion_message(self, stack_trace: str) -> str:
        """
        Extract assertion message from stack trace if present.
        
        Args:
            stack_trace: Full stack trace text
            
        Returns:
            Assertion message or empty string
        """
        if not stack_trace:
            return ""
        
        # Common assertion message patterns
        patterns = [
            r'AssertionError:\s*(.+?)(?:\n|$)',
            r'expected:<(.+?)>\s*but was:<(.+?)>',
            r'Expected\s+(.+?)\s+but\s+(?:got|was|received)\s+(.+?)(?:\n|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, stack_trace, re.IGNORECASE)
            if match:
                return match.group(0)[:200]  # Limit length
        
        return ""
    
    def filter_framework_frames(self, stack_trace: str) -> str:
        """
        Remove generic framework frames to focus on application-specific traces.
        
        Args:
            stack_trace: Full stack trace text
            
        Returns:
            Filtered stack trace with framework frames removed
        """
        if not stack_trace:
            return ""
        
        lines = stack_trace.split('\n')
        filtered = []
        
        for line in lines:
            # Skip framework frames
            is_framework = any(re.search(p, line) for p in self.FRAMEWORK_PATTERNS)
            if not is_framework:
                filtered.append(line)
        
        # If we filtered everything, keep original (first few lines at least)
        if not filtered and lines:
            return '\n'.join(lines[:5])
        
        return '\n'.join(filtered)
    
    def extract_test_package(self, class_name: str) -> str:
        """
        Extract the test package/domain from class name.
        
        Args:
            class_name: Full class name (e.g., android.view.cts.TooltipTest)
            
        Returns:
            Package domain (e.g., 'android.view.cts')
        """
        if not class_name:
            return ""
        
        parts = class_name.rsplit('.', 1)
        return parts[0] if len(parts) > 1 else ""
    
    def create_enriched_features(
        self, 
        failures: List[Dict]
    ) -> List[str]:
        """
        Create enriched text features for clustering.
        
        This is the key improvement: we weight domain information by repetition
        to ensure module/class context influences clustering more than generic 
        framework traces.
        
        Args:
            failures: List of dicts with keys:
                - module_name: CTS module (e.g., CtsViewTestCases)
                - class_name: Test class (e.g., android.view.cts.TooltipTest)
                - method_name: Test method (e.g., testTooltipDisplay)
                - stack_trace: Full stack trace
                - error_message: Error message if available
        
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
            assertion_msg = self.extract_assertion_message(stack)
            filtered_stack = self.filter_framework_frames(stack)
            test_package = self.extract_test_package(class_name)
            
            # Get simple class name (without package)
            simple_class = class_name.split('.')[-1] if class_name else ''
            
            # Weight important features by repetition
            # Module is most important (3x), then class (2x), then exception
            # This ensures domain context influences clustering
            enriched = f"""
{module} {module} {module}
{test_package} {test_package}
{simple_class} {simple_class}
{method}
{exception_type} {exception_type}
{assertion_msg}
{error}
{filtered_stack[:800]}
"""
            enriched_texts.append(enriched.strip())
        
        return enriched_texts
    
    def cluster_failures(
        self, 
        failures: List[Dict]
    ) -> Tuple[List[int], Dict[str, Any]]:
        """
        Cluster failures using enriched features and HDBSCAN.
        
        Args:
            failures: List of failure dicts (see create_enriched_features)
        
        Returns:
            Tuple of:
            - labels: List of cluster assignments (-1 for outliers with HDBSCAN)
            - metrics: Dict containing clustering quality information
        """
        if not failures:
            return [], {'n_clusters': 0, 'method': 'empty'}
        
        enriched_texts = self.create_enriched_features(failures)
        
        # Filter empty texts
        valid_mask = [bool(t.strip()) for t in enriched_texts]
        valid_texts = [t for t, v in zip(enriched_texts, valid_mask) if v]
        
        if not valid_texts:
            labels = [0] * len(failures)
            self._last_metrics = {'n_clusters': 1, 'method': 'all_empty_fallback'}
            return labels, self._last_metrics
        
        if len(valid_texts) == 1:
            # Single failure, assign to cluster 0
            labels = [0 if v else -1 for v in valid_mask]
            self._last_metrics = {'n_clusters': 1, 'method': 'single_sample'}
            return labels, self._last_metrics
        
        try:
            # Vectorize with TF-IDF
            tfidf_matrix = self.vectorizer.fit_transform(valid_texts)
            
            if self.use_hdbscan:
                labels, metrics = self._cluster_hdbscan(tfidf_matrix, valid_texts)
            else:
                labels, metrics = self._cluster_kmeans(tfidf_matrix, valid_texts)
            
            # Map back to original indices (mark invalid as outliers)
            full_labels = []
            valid_idx = 0
            for is_valid in valid_mask:
                if is_valid:
                    full_labels.append(int(labels[valid_idx]))
                    valid_idx += 1
                else:
                    full_labels.append(-1)
            
            self._last_metrics = metrics
            return full_labels, metrics
            
        except Exception as e:
            print(f"Clustering failed: {e}")
            import traceback
            traceback.print_exc()
            labels = [0] * len(failures)
            self._last_metrics = {'n_clusters': 1, 'method': 'error', 'error': str(e)}
            return labels, self._last_metrics
    
    def _cluster_hdbscan(
        self, 
        tfidf_matrix, 
        texts: List[str]
    ) -> Tuple[List[int], Dict[str, Any]]:
        """
        Perform HDBSCAN clustering.
        
        HDBSCAN automatically determines the optimal number of clusters
        and can identify outliers (noise points with label=-1).
        """
        # Convert sparse matrix to dense for HDBSCAN
        dense_matrix = tfidf_matrix.toarray()
        
        clusterer = HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
            metric='euclidean',
            cluster_selection_method='eom',  # Excess of Mass
            prediction_data=False
        )
        
        labels = clusterer.fit_predict(dense_matrix)
        
        # Calculate metrics
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_outliers = int(np.sum(labels == -1))
        n_samples = len(labels)
        
        # Calculate silhouette score if we have valid clusters
        silhouette = -1.0
        if n_clusters >= 2 and n_samples - n_outliers >= 2:
            try:
                # Only use non-outlier points for silhouette
                valid_mask = labels != -1
                if np.sum(valid_mask) >= 2:
                    silhouette = float(silhouette_score(
                        dense_matrix[valid_mask], 
                        labels[valid_mask]
                    ))
            except:
                pass
        
        metrics = {
            'method': 'hdbscan',
            'n_clusters': n_clusters,
            'n_outliers': n_outliers,
            'n_samples': n_samples,
            'outlier_ratio': n_outliers / n_samples if n_samples > 0 else 0,
            'silhouette_score': silhouette
        }
        
        return labels.tolist(), metrics
    
    def _cluster_kmeans(
        self, 
        tfidf_matrix, 
        texts: List[str]
    ) -> Tuple[List[int], Dict[str, Any]]:
        """
        Fallback KMeans clustering when HDBSCAN is not available.
        
        Uses a heuristic to determine cluster count.
        """
        n_samples = tfidf_matrix.shape[0]
        
        # Heuristic: sqrt(n/2) clusters, bounded
        n_clusters = max(2, min(20, int(np.sqrt(n_samples / 2)) + 1))
        
        if n_samples < n_clusters:
            n_clusters = max(1, n_samples // 2)
        
        kmeans = MiniBatchKMeans(
            n_clusters=n_clusters,
            random_state=42,
            batch_size=min(100, n_samples),
            n_init=3
        )
        
        labels = kmeans.fit_predict(tfidf_matrix)
        
        # Calculate silhouette score
        silhouette = -1.0
        if n_clusters >= 2 and n_samples >= 2:
            try:
                silhouette = float(silhouette_score(tfidf_matrix, labels))
            except:
                pass
        
        metrics = {
            'method': 'kmeans',
            'n_clusters': n_clusters,
            'n_outliers': 0,
            'n_samples': n_samples,
            'outlier_ratio': 0,
            'silhouette_score': silhouette,
            'inertia': float(kmeans.inertia_)
        }
        
        return labels.tolist(), metrics
    
    def handle_outliers(
        self, 
        failures: List[Dict], 
        labels: List[int]
    ) -> List[int]:
        """
        Handle outliers (label=-1) by grouping them by module_name.
        
        This provides a hierarchical fallback: if HDBSCAN can't cluster
        a failure, we at least group it with same-module failures.
        
        Args:
            failures: Original failure dicts
            labels: Cluster labels with -1 for outliers
            
        Returns:
            Updated labels with outliers assigned to module-based clusters
        """
        if -1 not in labels:
            return labels
        
        # Find max existing label
        max_label = max((l for l in labels if l >= 0), default=-1)
        
        # Group outliers by module
        module_clusters: Dict[str, int] = {}
        new_labels = list(labels)  # Make a copy
        
        for i, (label, failure) in enumerate(zip(labels, failures)):
            if label == -1:
                module = failure.get('module_name', 'Unknown') or 'Unknown'
                
                if module not in module_clusters:
                    max_label += 1
                    module_clusters[module] = max_label
                
                new_labels[i] = module_clusters[module]
        
        return new_labels
    
    def merge_small_clusters(
        self, 
        failures: List[Dict], 
        labels: List[int],
        max_merge_size: int = 2
    ) -> List[int]:
        """
        P1: Merge small clusters that share the same module+class.
        
        This reduces over-fragmentation where HDBSCAN creates many tiny clusters
        for failures that likely share the same root cause.
        
        Args:
            failures: Original failure dicts
            labels: Cluster labels
            max_merge_size: Maximum cluster size to consider for merging
            
        Returns:
            Updated labels with small same-class clusters merged
        """
        # Group by module+class
        class_groups: Dict[Tuple[str, str], List[Tuple[int, int]]] = defaultdict(list)
        for i, (f, label) in enumerate(zip(failures, labels)):
            key = (f.get('module_name', ''), f.get('class_name', ''))
            class_groups[key].append((i, label))
        
        new_labels = list(labels)
        
        for key, items in class_groups.items():
            if len(items) < 2:
                continue
                
            # Count cluster sizes within this class group
            cluster_sizes: Dict[int, int] = Counter(label for _, label in items)
            
            # Find small clusters to merge
            small_clusters = [c for c, size in cluster_sizes.items() if size <= max_merge_size]
            
            if len(small_clusters) > 1:
                # Merge all small clusters into the first one
                target = small_clusters[0]
                for i, label in items:
                    if label in small_clusters:
                        new_labels[i] = target
        
        # Re-label to ensure consecutive labels
        unique_labels = sorted(set(new_labels))
        label_map = {old: new for new, old in enumerate(unique_labels)}
        new_labels = [label_map[l] for l in new_labels]
        
        return new_labels
    
    def get_cluster_summary(
        self, 
        failures: List[Dict], 
        labels: List[int]
    ) -> Dict[int, Dict[str, Any]]:
        """
        Generate summary statistics for each cluster.
        
        Args:
            failures: Original failure dicts
            labels: Cluster labels
            
        Returns:
            Dict mapping cluster_id to summary info
        """
        cluster_info: Dict[int, Dict[str, Any]] = {}
        
        for failure, label in zip(failures, labels):
            if label not in cluster_info:
                cluster_info[label] = {
                    'count': 0,
                    'modules': set(),
                    'classes': set(),
                    'methods': [],
                    'exceptions': set()
                }
            
            info = cluster_info[label]
            info['count'] += 1
            
            module = failure.get('module_name', '')
            if module:
                info['modules'].add(module)
            
            class_name = failure.get('class_name', '')
            if class_name:
                info['classes'].add(class_name.split('.')[-1])  # Simple name
            
            method = failure.get('method_name', '')
            if method:
                info['methods'].append(method)
            
            stack = failure.get('stack_trace', '')
            exc = self.extract_exception_type(stack)
            if exc:
                info['exceptions'].add(exc.split('.')[-1])  # Simple name
        
        # Convert sets to lists for serialization
        for label, info in cluster_info.items():
            info['modules'] = list(info['modules'])
            info['classes'] = list(info['classes'])[:10]  # Limit
            info['exceptions'] = list(info['exceptions'])
            info['methods'] = info['methods'][:5]  # Sample methods
            
            # Calculate purity (single module = high purity)
            info['purity'] = 1.0 / len(info['modules']) if info['modules'] else 0
        
        return cluster_info
    
    @property
    def last_metrics(self) -> Dict[str, Any]:
        """Get metrics from the last clustering operation."""
        return self._last_metrics


# Backward compatibility: Keep original class name as alias
class FailureClusterer(ImprovedFailureClusterer):
    """
    Legacy compatibility wrapper.
    
    The original FailureClusterer only took List[str] of stack traces.
    This wrapper maintains that interface while using the improved algorithm.
    """
    
    def __init__(self, n_clusters: int = 10):
        """
        Initialize with legacy interface.
        
        Note: n_clusters is ignored when using HDBSCAN (which auto-determines clusters).
        It's kept for API compatibility.
        """
        super().__init__(
            min_cluster_size=2,
            use_hdbscan=HDBSCAN_AVAILABLE
        )
        self._legacy_n_clusters = n_clusters
    
    def cluster_failures(self, failures: List[str]) -> List[int]:
        """
        Legacy interface: cluster from stack trace strings only.
        
        This wraps the new interface for backward compatibility.
        Module/class information will be inferred from stack traces where possible.
        
        Args:
            failures: List of stack trace strings
            
        Returns:
            List of cluster labels
        """
        # Convert string list to dict format
        failure_dicts = []
        for trace in failures:
            # Try to extract module/class from stack trace
            module = ""
            class_name = ""
            method = ""
            
            # Look for test class in stack trace
            match = re.search(r'at\s+([\w.]+)\.(\w+)\(', trace)
            if match:
                class_name = match.group(1)
                method = match.group(2)
                
                # Try to infer module from class name pattern
                if 'cts' in class_name.lower():
                    parts = class_name.split('.')
                    for i, part in enumerate(parts):
                        if 'cts' in part.lower() and i > 0:
                            module = f"Cts{parts[i-1].title()}TestCases"
                            break
            
            failure_dicts.append({
                'module_name': module,
                'class_name': class_name,
                'method_name': method,
                'stack_trace': trace,
                'error_message': ''
            })
        
        labels, _ = super().cluster_failures(failure_dicts)
        
        # Handle outliers for legacy interface
        labels = self.handle_outliers(failure_dicts, labels)
        
        return labels
    
    def get_cluster_keywords(
        self, 
        failures: List[str], 
        labels: List[int]
    ) -> Dict[int, List[str]]:
        """
        Legacy interface for extracting cluster keywords.
        
        This is a stub that returns empty dict for compatibility.
        Use get_cluster_summary() on the new interface for richer info.
        """
        return {}
