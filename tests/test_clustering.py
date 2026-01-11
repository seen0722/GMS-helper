"""
Test module for ImprovedFailureClusterer

Run with: pytest tests/test_clustering.py -v
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.analysis.clustering import ImprovedFailureClusterer, FailureClusterer


class TestExceptionExtraction:
    """Test exception type extraction from stack traces."""
    
    def setup_method(self):
        self.clusterer = ImprovedFailureClusterer()
    
    def test_basic_assertion_error(self):
        stack = """java.lang.AssertionError
        at org.junit.Assert.fail(Assert.java:87)
        at android.test.MyTest.testMethod(MyTest.java:42)"""
        
        result = self.clusterer.extract_exception_type(stack)
        assert result == "java.lang.AssertionError"
    
    def test_nested_exception(self):
        stack = """java.lang.RuntimeException: Test failed
        at Something.method()
        Caused by: java.lang.NullPointerException
        at Other.method()"""
        
        result = self.clusterer.extract_exception_type(stack)
        # Should find first exception
        assert "RuntimeException" in result or "NullPointerException" in result
    
    def test_assertion_with_message(self):
        stack = """java.lang.AssertionError: expected:<true> but was:<false>
        at org.junit.Assert.fail(Assert.java:87)"""
        
        result = self.clusterer.extract_exception_type(stack)
        assert result == "java.lang.AssertionError"
    
    def test_empty_stack(self):
        result = self.clusterer.extract_exception_type("")
        assert result == ""
    
    def test_no_exception(self):
        result = self.clusterer.extract_exception_type("Some random text")
        assert result == ""


class TestFrameworkFiltering:
    """Test filtering of framework stack frames."""
    
    def setup_method(self):
        self.clusterer = ImprovedFailureClusterer()
    
    def test_filters_junit_frames(self):
        stack = """java.lang.AssertionError
        at org.junit.Assert.fail(Assert.java:87)
        at org.junit.Assert.assertTrue(Assert.java:42)
        at android.view.cts.TooltipTest.testTooltip(TooltipTest.java:100)"""
        
        result = self.clusterer.filter_framework_frames(stack)
        
        assert "org.junit.Assert" not in result
        assert "TooltipTest" in result
    
    def test_preserves_app_frames(self):
        stack = """at android.view.cts.TooltipTest.testTooltip(TooltipTest.java:100)
        at android.view.cts.TooltipTest.helper(TooltipTest.java:50)"""
        
        result = self.clusterer.filter_framework_frames(stack)
        
        assert "TooltipTest" in result
        assert len(result.strip().split('\n')) == 2


class TestEnrichedFeatures:
    """Test enriched feature generation."""
    
    def setup_method(self):
        self.clusterer = ImprovedFailureClusterer()
    
    def test_includes_module_name(self):
        failures = [{
            'module_name': 'CtsViewTestCases',
            'class_name': 'android.view.cts.TooltipTest',
            'method_name': 'testTooltipDisplay',
            'stack_trace': 'java.lang.AssertionError',
            'error_message': ''
        }]
        
        features = self.clusterer.create_enriched_features(failures)
        
        assert len(features) == 1
        # Module should appear multiple times (weighted)
        assert features[0].count('CtsViewTestCases') >= 2
    
    def test_includes_class_name(self):
        failures = [{
            'module_name': '',
            'class_name': 'android.view.cts.TooltipTest',
            'method_name': '',
            'stack_trace': '',
            'error_message': 'Test error'
        }]
        
        features = self.clusterer.create_enriched_features(failures)
        
        assert 'TooltipTest' in features[0]
        assert 'android.view.cts' in features[0]
    
    def test_handles_empty_failure(self):
        failures = [{
            'module_name': '',
            'class_name': '',
            'method_name': '',
            'stack_trace': '',
            'error_message': ''
        }]
        
        features = self.clusterer.create_enriched_features(failures)
        
        assert len(features) == 1
        # Should not crash, just return empty-ish text


class TestClustering:
    """Test clustering functionality."""
    
    def setup_method(self):
        self.clusterer = ImprovedFailureClusterer(min_cluster_size=2)
    
    def test_same_module_clusters_together(self):
        """Failures from same module should cluster together."""
        failures = [
            {
                'module_name': 'CtsNfcTestCases',
                'class_name': 'android.nfc.cts.NfcAdapterTest',
                'method_name': 'testMethod1',
                'stack_trace': 'java.lang.AssertionError\n  at android.nfc.cts.Test',
                'error_message': ''
            },
            {
                'module_name': 'CtsNfcTestCases',
                'class_name': 'android.nfc.cts.NfcAdapterTest',
                'method_name': 'testMethod2',
                'stack_trace': 'java.lang.AssertionError\n  at android.nfc.cts.Test',
                'error_message': ''
            },
            {
                'module_name': 'CtsViewTestCases',
                'class_name': 'android.view.cts.ViewTest',
                'method_name': 'testMethod1',
                'stack_trace': 'java.lang.AssertionError\n  at android.view.cts.Test',
                'error_message': ''
            },
            {
                'module_name': 'CtsViewTestCases',
                'class_name': 'android.view.cts.ViewTest',
                'method_name': 'testMethod2',
                'stack_trace': 'java.lang.AssertionError\n  at android.view.cts.Test',
                'error_message': ''
            },
        ]
        
        labels, metrics = self.clusterer.cluster_failures(failures)
        labels = self.clusterer.handle_outliers(failures, labels)
        
        # NFC tests should be in same cluster
        assert labels[0] == labels[1], "NFC tests should cluster together"
        
        # View tests should be in same cluster
        assert labels[2] == labels[3], "View tests should cluster together"
        
        # NFC and View should be different clusters (or at least handled)
        # Note: With small sample, HDBSCAN might mark all as outliers
        # In that case, our module-based fallback should differentiate them
        print(f"Labels: {labels}, Metrics: {metrics}")
    
    def test_empty_input(self):
        """Empty input should return empty labels."""
        labels, metrics = self.clusterer.cluster_failures([])
        
        assert labels == []
        assert metrics['n_clusters'] == 0
    
    def test_single_failure(self):
        """Single failure should get cluster 0."""
        failures = [{
            'module_name': 'CtsTest',
            'class_name': 'Test',
            'method_name': 'test',
            'stack_trace': 'Error',
            'error_message': ''
        }]
        
        labels, metrics = self.clusterer.cluster_failures(failures)
        
        assert len(labels) == 1
        assert labels[0] == 0


class TestOutlierHandling:
    """Test outlier handling functionality."""
    
    def setup_method(self):
        self.clusterer = ImprovedFailureClusterer()
    
    def test_outliers_grouped_by_module(self):
        """Outliers should be grouped by module name."""
        failures = [
            {'module_name': 'ModuleA', 'class_name': '', 'method_name': '', 'stack_trace': '', 'error_message': ''},
            {'module_name': 'ModuleA', 'class_name': '', 'method_name': '', 'stack_trace': '', 'error_message': ''},
            {'module_name': 'ModuleB', 'class_name': '', 'method_name': '', 'stack_trace': '', 'error_message': ''},
        ]
        
        # All marked as outliers initially
        labels = [-1, -1, -1]
        
        new_labels = self.clusterer.handle_outliers(failures, labels)
        
        # ModuleA items should have same label
        assert new_labels[0] == new_labels[1]
        
        # ModuleB should be different
        assert new_labels[2] != new_labels[0]
    
    def test_no_outliers_unchanged(self):
        """Labels without outliers should be unchanged."""
        failures = [
            {'module_name': 'M1', 'class_name': '', 'method_name': '', 'stack_trace': '', 'error_message': ''},
            {'module_name': 'M2', 'class_name': '', 'method_name': '', 'stack_trace': '', 'error_message': ''},
        ]
        
        labels = [0, 1]
        
        new_labels = self.clusterer.handle_outliers(failures, labels)
        
        assert new_labels == [0, 1]


class TestLegacyInterface:
    """Test backward compatibility with legacy FailureClusterer interface."""
    
    def test_legacy_string_input(self):
        """Legacy interface should work with string list."""
        clusterer = FailureClusterer(n_clusters=5)
        
        failures = [
            "java.lang.AssertionError\n  at android.nfc.cts.NfcTest.test(NfcTest.java:100)",
            "java.lang.AssertionError\n  at android.nfc.cts.NfcTest.test2(NfcTest.java:200)",
            "java.lang.NullPointerException\n  at android.view.cts.ViewTest.test(ViewTest.java:50)",
        ]
        
        labels = clusterer.cluster_failures(failures)
        
        assert len(labels) == 3
        assert all(isinstance(l, int) for l in labels)
    
    def test_legacy_empty_keywords(self):
        """Legacy get_cluster_keywords should return empty dict."""
        clusterer = FailureClusterer()
        
        result = clusterer.get_cluster_keywords(["trace1", "trace2"], [0, 0])
        
        assert result == {}


class TestClusterSummary:
    """Test cluster summary generation."""
    
    def setup_method(self):
        self.clusterer = ImprovedFailureClusterer()
    
    def test_summary_counts(self):
        failures = [
            {'module_name': 'M1', 'class_name': 'C1', 'method_name': 'm1', 'stack_trace': 'java.lang.AssertionError', 'error_message': ''},
            {'module_name': 'M1', 'class_name': 'C2', 'method_name': 'm2', 'stack_trace': 'java.lang.AssertionError', 'error_message': ''},
            {'module_name': 'M2', 'class_name': 'C3', 'method_name': 'm3', 'stack_trace': 'java.lang.NullPointerException', 'error_message': ''},
        ]
        labels = [0, 0, 1]
        
        summary = self.clusterer.get_cluster_summary(failures, labels)
        
        assert 0 in summary
        assert 1 in summary
        assert summary[0]['count'] == 2
        assert summary[1]['count'] == 1
        assert 'M1' in summary[0]['modules']
        assert 'M2' in summary[1]['modules']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
