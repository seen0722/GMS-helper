
import sqlite3
import os
import re
from datetime import datetime

DB_PATH = 'gms_analysis.db'
OUTPUT_FILE = 'docs/AI_PERFORMANCE_EVALUATION.md'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def calculate_metrics():
    conn = get_db_connection()
    
    # 1. Compression Metrics
    total_failures = conn.execute("SELECT COUNT(*) FROM test_cases WHERE status = 'fail'").fetchone()[0]
    total_clusters = conn.execute("SELECT COUNT(*) FROM failure_clusters").fetchone()[0]
    
    if total_failures == 0:
        compression_ratio = 0
    elif total_clusters == 0:
        compression_ratio = 0
    else:
        compression_ratio = (total_failures - total_clusters) / total_failures * 100

    # 2. Confidence Metrics
    # confidence_score is in failure_clusters table
    confidence_stats = conn.execute("""
        SELECT 
            AVG(confidence_score) as avg_conf,
            MIN(confidence_score) as min_conf,
            MAX(confidence_score) as max_conf
        FROM failure_clusters
    """).fetchone()

    # 3. Categorization Metrics
    categories = conn.execute("""
        SELECT category, COUNT(*) as count 
        FROM failure_clusters 
        GROUP BY category 
        ORDER BY count DESC
    """).fetchall()

    severities = conn.execute("""
        SELECT severity, COUNT(*) as count 
        FROM failure_clusters 
        GROUP BY severity 
        ORDER BY count DESC
    """).fetchall()

    return {
        "total_failures": total_failures,
        "total_clusters": total_clusters,
        "compression_ratio": compression_ratio,
        "confidence": confidence_stats,
        "categories": categories,
        "severities": severities
    }

def extract_manual_metrics():
    if not os.path.exists(OUTPUT_FILE):
        return {}
        
    with open(OUTPUT_FILE, 'r') as f:
        content = f.read()
        
    metrics = {}
    
    # Extract Accuracy
    acc_match = re.search(r"- \*\*Classification Accuracy:\*\* \*\*(.+?)\*\*", content)
    if not acc_match:
         acc_match = re.search(r"- \*\*Accuracy Score:\*\* \*\*(.+?)\*\*", content)
    if acc_match:
        metrics['accuracy'] = acc_match.group(1)
        
    # Extract Precision
    prec_match = re.search(r"- \*\*Cluster Purity \(Precision\):\*\* \*\*(.+?)\*\*", content)
    if not prec_match:
        prec_match = re.search(r"- \*\*Precision \(Cluster Purity\):\*\* \*\*(.+?)\*\*", content)
    if prec_match:
        metrics['precision'] = prec_match.group(1)
        
    # Extract Recall
    recall_match = re.search(r"- \*\*Cluster Recall \(Completeness\):\*\* \*\*(.+?)\*\*", content)
    if not recall_match:
        recall_match = re.search(r"- \*\*Recall \(Cluster Completeness\):\*\* \*\*(.+?)\*\*", content)
    if recall_match:
        metrics['recall'] = recall_match.group(1)
        
    return metrics

def generate_markdown(metrics, manual_metrics):
    md = "# AI Performance Evaluation Index Report\n\n"
    md += f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    # Section 1: Efficiency (Compression)
    md += "## 1. Efficiency Metrics (Compression)\n\n"
    md += "Measures how effectively the system reduces the workload (Compression Ratio).\n\n"
    md += f"- **Total Base Failures:** {metrics['total_failures']}\n"
    md += f"- **Total Clusters Generated:** {metrics['total_clusters']}\n"
    md += f"- **Compression Ratio:** **{metrics['compression_ratio']:.2f}%**\n\n"
    md += "*Note: Higher is better. 80% means 4/5ths of the logs are handled automatically.*\n\n"

    # Section 2: Quality & Reliability (Precision, Recall, Accuracy)
    md += "## 2. Quality Metrics (Precision & Recall)\n\n"
    md += "Validated by human experts to ensure the AI's trustworthiness.\n\n"
    
    # Precision (Purity)
    prec = manual_metrics.get('precision', 'Not Verified')
    md += f"- **Cluster Purity (Precision):** **{prec}**\n"
    md += "  *Are failures in a cluster actually the same issue?*\n\n"
    
    # Recall (Fragmentation)
    recall = manual_metrics.get('recall', 'Not Verified')
    md += f"- **Cluster Recall (Completeness):** **{recall}**\n"
    md += "  *Did we capture all instances of this bug in one group?*\n\n"
    
    # Accuracy (Root Cause)
    acc = manual_metrics.get('accuracy', 'Not Verified')
    md += f"- **Classification Accuracy:** **{acc}**\n"
    md += "  *Is the AI-predicted Root Cause correct?*\n\n"
    
    md += "*To update these metrics, run `python verify_ai_accuracy.py`*\n\n"

    # Conclusion
    md += "## 3. Conclusion\n\n"
    md += "Evaluating the current data set:\n"
    md += f"1.  **Efficiency**: The system successfully reduced workload by **{metrics['compression_ratio']:.1f}%**.\n"
    
    quality_summary = "verified High" if manual_metrics.get('precision') == '100.00%' else "being verified"
    md += f"2.  **Quality**: The clustering precision is **{manual_metrics.get('precision', 'Pending')}**.\n"

    return md

if __name__ == "__main__":
    db_metrics = calculate_metrics()
    manual_metrics = extract_manual_metrics()
    report = generate_markdown(db_metrics, manual_metrics)
    with open(OUTPUT_FILE, 'w') as f:
        f.write(report)
    print(f"Report generated (enhanced) at {OUTPUT_FILE}")
