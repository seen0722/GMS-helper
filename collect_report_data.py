
import sqlite3
import os

DB_PATH = 'gms_analysis.db'
OUTPUT_FILE = 'docs/REAL_DATA_ANALYSIS_REPORT.md'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def generate_report():
    conn = get_db_connection()
    
    report_content = "# Real Data Analysis Report\n\n"
    report_content += "This report contains real data collected from Test Run #1 and Test Run #2.\n\n"

    run_ids = [1, 2]
    
    for run_id in run_ids:
        # Get Run Info
        run = conn.execute('SELECT * FROM test_runs WHERE id = ?', (run_id,)).fetchone()
        
        if not run:
            report_content += f"## Test Run #{run_id}\n\n*Run not found in database.*\n\n"
            continue
            
        report_content += f"## Test Run #{run_id}\n\n"
        report_content += f"- **Suite:** {run['test_suite_name']}\n"
        report_content += f"- **Device:** {run['build_model']} ({run['build_product']})\n"
        report_content += f"- **Date:** {run['start_time']}\n"
        report_content += f"- **Failures:** {run['failed_tests']}\n\n"

        # Get Clusters for this run
        # Join test_cases -> failure_analysis -> failure_clusters
        query = """
            SELECT DISTINCT fc.* 
            FROM failure_clusters fc
            JOIN failure_analysis fa ON fc.id = fa.cluster_id
            JOIN test_cases tc ON fa.test_case_id = tc.id
            WHERE tc.test_run_id = ?
            ORDER BY fc.severity, fc.id
        """
        clusters = conn.execute(query, (run_id,)).fetchall()
        
        if not clusters:
             report_content += "*No clusters found for this run (Analysis might be pending).*\n\n"
             continue

        report_content += f"### Clusters Analysis ({len(clusters)} clusters)\n\n"
        
        for cluster in clusters:
            report_content += f"#### Cluster {cluster['id']}: {cluster['category']} ({cluster['severity']})\n\n"
            
            # Get sample failures for this cluster in this run
            fail_query = """
                SELECT tc.module_name, tc.class_name, tc.method_name, tc.error_message
                FROM test_cases tc
                JOIN failure_analysis fa ON tc.id = fa.test_case_id
                WHERE fa.cluster_id = ? AND tc.test_run_id = ?
                LIMIT 3
            """
            failures = conn.execute(fail_query, (cluster['id'], run_id)).fetchall()
            
            report_content += "**Sample Failures:**\n"
            for fail in failures:
                report_content += f"- `{fail['module_name']}`: {fail['class_name']}#{fail['method_name']}\n"
                if fail['error_message']:
                    report_content += f"  - *Error:* `{fail['error_message'][:100]}...`\n"
            report_content += "\n"

            report_content += "**AI Analysis:**\n"
            report_content += "```json\n"
            # It seems 'ai_summary' in table is text, but user wants json format if possible or just the summary
            # The schema shows ai_summary as TEXT. In previous steps, it seemed like a JSON string or unstructured text.
            # Let's try to interpret common column fields that map to the requested format.
            
            ai_output = {
                "description": cluster['description'],
                "root_cause": cluster['common_root_cause'],
                "solution": cluster['common_solution'],
                "ai_summary": cluster['ai_summary'],
                "severity": cluster['severity'],
                "category": cluster['category'],
                "confidence_score": cluster['confidence_score'],
                "suggested_assignment": cluster['suggested_assignment']
            }
            
            import json
            report_content += json.dumps(ai_output, indent=2)
            report_content += "\n```\n\n"
            report_content += "---\n\n"

    with open(OUTPUT_FILE, 'w') as f:
        f.write(report_content)
    
    print(f"Report generated at {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_report()
