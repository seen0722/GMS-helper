#!/usr/bin/env python3
"""
Validation script to compare clustering results before and after algorithm improvement.

This script:
1. Loads Run #35 failure data from the database
2. Runs the improved clustering algorithm
3. Compares with original clustering results
4. Generates a comparison report

Usage:
    python validate_clustering_improvement.py
"""

import sqlite3
import json
from collections import defaultdict

# Add project to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.analysis.clustering import ImprovedFailureClusterer


def get_original_clustering(db_path: str, run_id: int):
    """Get original clustering results from database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get failures with their cluster assignments
    query = """
    SELECT 
        tc.id,
        tc.module_name,
        tc.class_name,
        tc.method_name,
        tc.stack_trace,
        tc.error_message,
        fa.cluster_id,
        fc.category,
        fc.severity,
        fc.ai_summary
    FROM test_cases tc
    LEFT JOIN failure_analysis fa ON tc.id = fa.test_case_id
    LEFT JOIN failure_clusters fc ON fa.cluster_id = fc.id
    WHERE tc.test_run_id = ?
    ORDER BY tc.id
    """
    
    cursor.execute(query, (run_id,))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results


def run_improved_clustering(failures: list):
    """Run the improved clustering algorithm."""
    clusterer = ImprovedFailureClusterer(min_cluster_size=2)
    
    # Prepare data
    failure_dicts = [
        {
            'module_name': f.get('module_name', '') or '',
            'class_name': f.get('class_name', '') or '',
            'method_name': f.get('method_name', '') or '',
            'stack_trace': f.get('stack_trace', '') or '',
            'error_message': f.get('error_message', '') or ''
        }
        for f in failures
    ]
    
    # Cluster
    labels, metrics = clusterer.cluster_failures(failure_dicts)
    labels = clusterer.handle_outliers(failure_dicts, labels)
    
    # Get summary
    summary = clusterer.get_cluster_summary(failure_dicts, labels)
    
    return labels, metrics, summary


def analyze_cluster_purity(failures: list, labels: list, label_key: str = 'new'):
    """Analyze cluster purity based on module distribution."""
    cluster_modules = defaultdict(lambda: defaultdict(int))
    
    for f, label in zip(failures, labels):
        module = f.get('module_name', 'Unknown') or 'Unknown'
        cluster_modules[label][module] += 1
    
    purity_scores = {}
    for cluster_id, modules in cluster_modules.items():
        total = sum(modules.values())
        max_module_count = max(modules.values())
        purity = max_module_count / total if total > 0 else 0
        purity_scores[cluster_id] = {
            'purity': purity,
            'total': total,
            'dominant_module': max(modules, key=modules.get),
            'modules': dict(modules)
        }
    
    return purity_scores


def generate_report(original_data, new_labels, new_metrics, new_summary):
    """Generate comparison report."""
    print("=" * 80)
    print("CLUSTERING IMPROVEMENT VALIDATION REPORT")
    print("=" * 80)
    print()
    
    # Original clustering stats
    original_clusters = defaultdict(list)
    for f in original_data:
        cluster_id = f.get('cluster_id')
        if cluster_id is not None:
            original_clusters[cluster_id].append(f)
    
    print(f"📊 ORIGINAL CLUSTERING (Run #35)")
    print(f"   Total failures: {len(original_data)}")
    print(f"   Number of clusters: {len(original_clusters)}")
    print()
    
    # Analyze original purity
    original_labels = [f.get('cluster_id', -1) for f in original_data]
    original_purity = analyze_cluster_purity(original_data, original_labels)
    
    # Find problematic clusters (low purity)
    print("   🔴 Problematic Clusters (purity < 0.8):")
    for cluster_id, info in sorted(original_purity.items()):
        if info['purity'] < 0.8 and info['total'] >= 3:
            print(f"      Cluster #{cluster_id}: {info['total']} failures, "
                  f"purity={info['purity']:.2f}, modules={list(info['modules'].keys())}")
    print()
    
    # New clustering stats
    print(f"📊 IMPROVED CLUSTERING")
    print(f"   Method: {new_metrics.get('method', 'unknown')}")
    print(f"   Number of clusters: {new_metrics.get('n_clusters', 0)}")
    print(f"   Outliers: {new_metrics.get('n_outliers', 0)}")
    print(f"   Silhouette Score: {new_metrics.get('silhouette_score', -1):.3f}")
    print()
    
    # Analyze new purity
    new_purity = analyze_cluster_purity(original_data, new_labels)
    
    # Show improved clusters
    print("   ✅ Cluster Summary:")
    for cluster_id in sorted(new_summary.keys()):
        info = new_summary[cluster_id]
        purity_info = new_purity.get(cluster_id, {})
        purity = purity_info.get('purity', 0)
        status = "✅" if purity >= 0.8 else "⚠️" if purity >= 0.5 else "❌"
        print(f"      {status} Cluster #{cluster_id}: {info['count']} failures, "
              f"purity={purity:.2f}, modules={info['modules'][:3]}")
    print()
    
    # Overall comparison
    print("📈 COMPARISON")
    
    original_avg_purity = sum(
        p['purity'] * p['total'] for p in original_purity.values()
    ) / len(original_data) if original_data else 0
    
    new_avg_purity = sum(
        p['purity'] * p['total'] for p in new_purity.values()
    ) / len(original_data) if original_data else 0
    
    print(f"   Original weighted avg purity: {original_avg_purity:.3f}")
    print(f"   Improved weighted avg purity: {new_avg_purity:.3f}")
    print(f"   Improvement: {(new_avg_purity - original_avg_purity) * 100:.1f}%")
    print()
    
    # Specific example: Check cluster #22 (the catch-all)
    print("🔍 SPECIFIC CHECK: Original Cluster #22 (Catch-all Problem)")
    cluster_22_failures = [f for f in original_data if f.get('cluster_id') == 22]
    if cluster_22_failures:
        print(f"   Original had {len(cluster_22_failures)} failures in cluster #22")
        
        # Find where these ended up in new clustering
        cluster_22_indices = [i for i, f in enumerate(original_data) if f.get('cluster_id') == 22]
        new_cluster_dist = defaultdict(int)
        for idx in cluster_22_indices:
            new_cluster_dist[new_labels[idx]] += 1
        
        print(f"   After improvement, split into {len(new_cluster_dist)} clusters:")
        for new_cluster, count in sorted(new_cluster_dist.items(), key=lambda x: -x[1]):
            cluster_info = new_summary.get(new_cluster, {})
            modules = cluster_info.get('modules', [])
            print(f"      → New Cluster #{new_cluster}: {count} failures, modules={modules[:2]}")
    
    print()
    print("=" * 80)


def main():
    db_path = "gms_analysis.db"
    run_id = 35
    
    print(f"Loading data for Run #{run_id}...")
    original_data = get_original_clustering(db_path, run_id)
    
    if not original_data:
        print(f"No data found for Run #{run_id}")
        return
    
    print(f"Found {len(original_data)} failures")
    print()
    
    print("Running improved clustering algorithm...")
    new_labels, new_metrics, new_summary = run_improved_clustering(original_data)
    
    print()
    generate_report(original_data, new_labels, new_metrics, new_summary)


if __name__ == '__main__':
    main()
