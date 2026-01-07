
import sqlite3
import random
import os

DB_PATH = 'gms_analysis.db'
REPORT_PATH = 'docs/AI_PERFORMANCE_EVALUATION.md'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def verify_accuracy(sample_size=5):
    conn = get_db_connection()
    
    # Fetch all clusters with their sample failures
    query = """
        SELECT fc.id, fc.category, fc.common_root_cause, fc.ai_summary,
               tc.error_message, tc.module_name, tc.class_name
        FROM failure_clusters fc
        JOIN failure_analysis fa ON fc.id = fa.cluster_id
        JOIN test_cases tc ON fa.test_case_id = tc.id
        GROUP BY fc.id
    """
    clusters = conn.execute(query).fetchall()
    
    if not clusters:
        print("No clusters found to verify.")
        return

    # Select random samples
    samples = random.sample(clusters, min(len(clusters), sample_size))
    
    print(f"\n--- AI Accuracy Verification (Sample Size: {len(samples)}) ---")
    print("Please verify if the AI analysis matches the failure error.\n")
    
    correct_count = 0
    
    for i, cluster in enumerate(samples, 1):
        print(f"Sample {i}/{len(samples)}")
        print(f"Failure: [{cluster['module_name']}] {cluster['class_name']}")
        print(f"Error: {cluster['error_message'][:200]}...")
        print("-" * 40)
        print(f"AI Category: {cluster['category']}")
        print(f"AI Root Cause: {cluster['common_root_cause']}")
        print("-" * 40)
        
        while True:
            choice = input("Is this analysis correct? (y/n): ").lower()
            if choice in ['y', 'n']:
                break
        
        if choice == 'y':
            correct_count += 1
        print("\n")

    accuracy = (correct_count / len(samples)) * 100
    print(f"Verification Complete!")
    print(f"Accuracy: {accuracy:.2f}% ({correct_count}/{len(samples)})")
    
    update_report(accuracy, len(samples))

def update_report(accuracy, sample_size):
    if not os.path.exists(REPORT_PATH):
        print(f"Report file {REPORT_PATH} not found.")
        return

    with open(REPORT_PATH, 'r') as f:
        content = f.read()

    new_section = f"\n## 4. Human Verification (Accuracy)\n\n"
    new_section += f"- **Verified Samples:** {sample_size}\n"
    new_section += f"- **Accuracy Score:** **{accuracy:.2f}%**\n"
    from datetime import datetime
    new_section += f"- **Date Verified:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    # Append or replace section
    if "## 4. Human Verification (Accuracy)" in content:
        print("Updating existing verification section...")
        # Simple string replacement for demo purposes, sophisticated regex could be better
        # For now, let's just append a new log entry if it exists, or just append to end
        with open(REPORT_PATH, 'a') as f:
             f.write(f"\n### Ongoing Verification ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n")
             f.write(f"- Samples: {sample_size}, Accuracy: **{accuracy:.2f}%**\n")
    else:
        # Insert before Conclusion if possible, or append
        if "## 4. Conclusion" in content:
            content = content.replace("## 4. Conclusion", new_section + "## 5. Conclusion")
        else:
            content += new_section
            
        with open(REPORT_PATH, 'w') as f:
            f.write(content)
            
    print(f"Report updated at {REPORT_PATH}")

    verify_accuracy(size)

def verify_clustering_purity(sample_size=3):
    conn = get_db_connection()
    
    # Get random clusters
    clusters = conn.execute("SELECT id, ai_summary FROM failure_clusters ORDER BY RANDOM() LIMIT ?", (sample_size,)).fetchall()
    
    if not clusters:
        print("No clusters found.")
        return

    print(f"\n--- Clustering Purity Check (Sample Size: {len(clusters)}) ---")
    print("For each cluster, check if ALL listed failures look similar (belong to the same issue).")
    
    pure_clusters = 0
    
    for i, cluster in enumerate(clusters, 1):
        cid = cluster['id']
        summary = cluster['ai_summary']
        
        # Get failures in this cluster
        failures = conn.execute("""
            SELECT tc.module_name, tc.class_name, tc.error_message
            FROM failure_analysis fa
            JOIN test_cases tc ON fa.test_case_id = tc.id
            WHERE fa.cluster_id = ?
            LIMIT 10
        """, (cid,)).fetchall()
        
        print(f"\nCluster {i}/{len(clusters)} [ID: {cid}]")
        print(f"Summary: {summary}")
        print("-" * 40)
        
        for j, f in enumerate(failures, 1):
            print(f"{j}. [{f['module_name']}] {f['class_name']}")
            print(f"   Error: {os.linesep.join(f['error_message'].splitlines()[:2])}...") # Show first 2 lines
        
        print("-" * 40)
        if len(failures) == 0:
            print("(No failures linked? This is an anomaly.)")
            continue
            
        while True:
            choice = input(f"Do these {len(failures)} failures belong to the same group? (y/n): ").lower()
            if choice in ['y', 'n']:
                break
        
        if choice == 'y':
            pure_clusters += 1

    print(f"\nVerification Complete!")
    print(f"Precision (Purity) Score: {purity_score:.2f}% ({pure_clusters}/{len(clusters)})")
    
    update_report_metric("Precision (Cluster Purity)", purity_score, len(clusters))

def verify_recall(sample_size=3):
    conn = get_db_connection()
    # Get random clusters
    clusters = conn.execute("SELECT id, ai_summary, common_root_cause FROM failure_clusters ORDER BY RANDOM() LIMIT ?", (sample_size,)).fetchall()

    if not clusters:
        print("No clusters found.")
        return

    print(f"\n--- Recall (Fragmentation) Check (Sample Size: {len(clusters)}) ---")
    print("For each cluster, we will search for OTHER clusters that look like duplicates.")
    print("If duplicates exist, it means the AI 'forgot' to group them together (Lower Recall).")

    total_recall_accum = 0

    for i, cluster in enumerate(clusters, 1):
        cid = cluster['id']
        summary = cluster['ai_summary']
        root_cause = cluster['common_root_cause']

        print(f"\nTarget Cluster {i}/{len(clusters)} [ID: {cid}]")
        print(f"Summary: {summary}")
        print(f"Root Cause: {root_cause}")
        print("-" * 40)

        # Simple heuristic: find other clusters with similar words in summary
        # In a real app, we'd use embedding similarity. Here we just list all *other* clusters
        # and ask user to scan them. For large DBs, this manual scan is hard, but valid for small N.
        
        other_clusters = conn.execute("SELECT id, ai_summary FROM failure_clusters WHERE id != ?", (cid,)).fetchall()
        
        if not other_clusters:
            print("No other clusters in DB. Recall is 100%.")
            total_recall_accum += 1
            continue

        print(f"Scanning {len(other_clusters)} other clusters for duplicates...")
        possible_dups = []
        
        # We display them in batches or just all if small
        # For simplicity, let's just show titles and ask user "How many match?"
        print("Other Clusters:")
        for oc in other_clusters:
            print(f" - [ID: {oc['id']}] {oc['ai_summary'][:80]}...")
        
        while True:
            try:
                dup_count = int(input(f"\nHow many of these are duplicates of Target [ID: {cid}]? (Enter 0 if unique): "))
                if dup_count >= 0:
                    break
            except ValueError:
                pass
        
        # Recall formula for this item: 1 / (1 + duplicates)
        # If 0 dups, recall = 1/1 = 100%
        # If 1 dup, recall = 1/2 = 50%
        instance_recall = 1.0 / (1.0 + dup_count)
        print(f" -> Instance Recall: {instance_recall*100:.1f}%")
        total_recall_accum += instance_recall

    avg_recall = (total_recall_accum / len(clusters)) * 100
    print(f"\nVerification Complete!")
    print(f"Recall (Completeness) Score: {avg_recall:.2f}%")
    
    update_report_metric("Recall (Cluster Completeness)", avg_recall, len(clusters))

def update_report_metric(metric_name, score, sample_size):
    if not os.path.exists(REPORT_PATH):
        print(f"Report file {REPORT_PATH} not found.")
        return

    with open(REPORT_PATH, 'r') as f:
        content = f.read()

    from datetime import datetime
    
    # We use a generic section updater
    # Map metric_name to a section header
    header_map = {
        "Precision (Cluster Purity)": "## 5. Precision & Recall Evaluation",
        "Recall (Cluster Completeness)": "## 5. Precision & Recall Evaluation"
    }
    
    header = header_map.get(metric_name, "## Other Metrics")
    
    # Check if the main header exists, if not create it
    if header not in content:
        # Insert before Conclusion
        if "## 6. Conclusion" in content:
            content = content.replace("## 6. Conclusion", f"{header}\n\n## 6. Conclusion")
        elif "## 5. Conclusion" in content: # Handle old version
            content = content.replace("## 5. Conclusion", f"{header}\n\n## 6. Conclusion")
        elif "## 4. Conclusion" in content: # Handle older version
            content = content.replace("## 4. Conclusion", f"{header}\n\n## 6. Conclusion")
        else:
             content += f"\n{header}\n\n"

    # Now we need to insert the specific metric line
    # We'll just perform a regex substitution or simple append for now
    # Ideally, we parse the markdown, but regex is faster for this script
    
    # If the metric line exists, update it
    import re
    metric_pattern = re.escape(f"- **{metric_name}:**") + r" .*"
    new_line = f"- **{metric_name}:** **{score:.2f}%** (Samples: {sample_size}, Date: {datetime.now().strftime('%Y-%m-%d %H:%M')})"
    
    if re.search(metric_pattern, content):
        content = re.sub(metric_pattern, new_line, content)
    else:
        # Append after the header
        # Find header position
        header_pos = content.find(header)
        # Find next newline after header
        insert_pos = content.find("\n", header_pos) + 1
        content = content[:insert_pos] + f"{new_line}\n" + content[insert_pos:]

    with open(REPORT_PATH, 'w') as f:
        f.write(content)
        
    print(f"Report updated at {REPORT_PATH}")

if __name__ == "__main__":
    print("Select Verification Mode:")
    print("1. AI Classification Accuracy (Root Cause check)")
    print("2. Precision Check (Cluster Purity)")
    print("3. Recall Check (Cluster Fragmentation)")
    
    mode = input("Enter 1, 2, or 3: ").strip()
    
    try:
        size = int(input("Enter sample size to verify (default 3): ") or 3)
    except ValueError:
        size = 3

    if mode == '2':
        verify_clustering_purity(size)
    elif mode == '3':
        verify_recall(size)
    else:
        verify_accuracy(size)
