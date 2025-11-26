#!/usr/bin/env python3
"""
GMS Analyzer CLI Tool
A simple command-line interface for the GMS Certification Analyzer

Usage:
    ./gms-cli.py list                    # List all test runs
    ./gms-cli.py count                   # Count total test runs
    ./gms-cli.py details <run_id>        # Get run details
    ./gms-cli.py upload <xml_file>       # Upload test result
    ./gms-cli.py analyze <run_id>        # Run AI analysis
    ./gms-cli.py status <run_id>         # Check analysis status
    ./gms-cli.py clusters <run_id>       # View failure clusters
    ./gms-cli.py delete <run_id>         # Delete a test run
"""

import sys
import requests
import json
from datetime import datetime
from pathlib import Path

# Configuration
API_BASE = "http://localhost:8000/api"

class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Print a colored header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.ENDC}\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.ENDC}")

def list_runs():
    """List all test runs"""
    try:
        response = requests.get(f"{API_BASE}/reports/runs")
        response.raise_for_status()
        runs = response.json()
        
        if not runs:
            print_info("No test runs found")
            return
        
        print_header(f"Test Runs ({len(runs)} total)")
        
        # Print table header
        print(f"{Colors.BOLD}{'ID':<5} {'Suite':<10} {'Tests':<10} {'Passed':<10} {'Failed':<10} {'Status':<12} {'Created':<20}{Colors.ENDC}")
        print("-" * 85)
        
        # Print each run
        for run in runs:
            status_color = Colors.GREEN if run['status'] == 'completed' else Colors.YELLOW
            print(f"{run['id']:<5} "
                  f"{run['test_suite_name']:<10} "
                  f"{run['total_tests']:<10} "
                  f"{Colors.GREEN}{run['passed_tests']:<10}{Colors.ENDC} "
                  f"{Colors.RED}{run['failed_tests']:<10}{Colors.ENDC} "
                  f"{status_color}{run['status']:<12}{Colors.ENDC} "
                  f"{run.get('created_at', 'N/A')[:19]:<20}")
        
    except requests.exceptions.RequestException as e:
        print_error(f"Failed to fetch runs: {e}")
        sys.exit(1)

def count_runs():
    """Count total test runs"""
    try:
        response = requests.get(f"{API_BASE}/reports/runs")
        response.raise_for_status()
        runs = response.json()
        
        total = len(runs)
        print_header("Test Run Statistics")
        print(f"Total test runs: {Colors.BOLD}{total}{Colors.ENDC}")
        
        # Count by suite
        suites = {}
        for run in runs:
            suite = run['test_suite_name']
            suites[suite] = suites.get(suite, 0) + 1
        
        if suites:
            print(f"\n{Colors.BOLD}By Suite:{Colors.ENDC}")
            for suite, count in sorted(suites.items()):
                print(f"  {suite}: {count}")
        
    except requests.exceptions.RequestException as e:
        print_error(f"Failed to count runs: {e}")
        sys.exit(1)

def get_run_details(run_id):
    """Get detailed information about a test run"""
    try:
        response = requests.get(f"{API_BASE}/reports/runs/{run_id}")
        response.raise_for_status()
        run = response.json()
        
        print_header(f"Test Run #{run_id} Details")
        
        # Basic info
        print(f"{Colors.BOLD}Suite:{Colors.ENDC} {run['test_suite_name']}")
        print(f"{Colors.BOLD}Status:{Colors.ENDC} {run['status']}")
        print(f"{Colors.BOLD}Analysis Status:{Colors.ENDC} {run.get('analysis_status', 'N/A')}")
        
        # Test statistics
        print(f"\n{Colors.BOLD}Test Statistics:{Colors.ENDC}")
        print(f"  Total Tests: {run['total_tests']}")
        print(f"  {Colors.GREEN}Passed: {run['passed_tests']}{Colors.ENDC}")
        print(f"  {Colors.RED}Failed: {run['failed_tests']}{Colors.ENDC}")
        if run.get('skipped_tests'):
            print(f"  Skipped: {run['skipped_tests']}")
        
        # Module statistics
        if run.get('total_modules'):
            print(f"\n{Colors.BOLD}Module Statistics:{Colors.ENDC}")
            print(f"  Total Modules: {run['total_modules']}")
            print(f"  {Colors.GREEN}Passed: {run.get('passed_modules', 0)}{Colors.ENDC}")
            print(f"  {Colors.RED}Failed: {run.get('failed_modules', 0)}{Colors.ENDC}")
        
        # Device info
        print(f"\n{Colors.BOLD}Device Information:{Colors.ENDC}")
        print(f"  Fingerprint: {run.get('device_fingerprint', 'N/A')}")
        print(f"  Build ID: {run.get('build_id', 'N/A')}")
        print(f"  Product: {run.get('build_product', 'N/A')}")
        print(f"  Model: {run.get('build_model', 'N/A')}")
        print(f"  Android Version: {run.get('android_version', 'N/A')}")
        
        # Timestamps
        if run.get('created_at'):
            print(f"\n{Colors.BOLD}Created:{Colors.ENDC} {run['created_at']}")
        
    except requests.exceptions.RequestException as e:
        print_error(f"Failed to fetch run details: {e}")
        sys.exit(1)

def upload_file(file_path):
    """Upload a test result XML file"""
    path = Path(file_path)
    
    if not path.exists():
        print_error(f"File not found: {file_path}")
        sys.exit(1)
    
    if not path.suffix.lower() == '.xml':
        print_error("File must be an XML file")
        sys.exit(1)
    
    print_info(f"Uploading {path.name}...")
    
    try:
        with open(path, 'rb') as f:
            files = {'file': (path.name, f, 'application/xml')}
            response = requests.post(f"{API_BASE}/upload/", files=files, timeout=300)
        
        response.raise_for_status()
        result = response.json()
        
        print_success(f"Upload successful!")
        print(f"Test Run ID: {Colors.BOLD}{result['test_run_id']}{Colors.ENDC}")
        print(f"Status: {result['status']}")
        print_info(f"View at: http://localhost:8000/?page=run-details&id={result['test_run_id']}")
        
    except requests.exceptions.Timeout:
        print_error("Upload timeout - file may be too large")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print_error(f"Upload failed: {e}")
        sys.exit(1)

def run_analysis(run_id):
    """Start AI analysis for a test run"""
    print_info(f"Starting AI analysis for run #{run_id}...")
    
    try:
        response = requests.post(f"{API_BASE}/analysis/run/{run_id}")
        response.raise_for_status()
        result = response.json()
        
        print_success("Analysis started!")
        print(f"Status: {result['status']}")
        print_info("Use 'gms-cli.py status <run_id>' to check progress")
        
    except requests.exceptions.RequestException as e:
        print_error(f"Failed to start analysis: {e}")
        sys.exit(1)

def check_status(run_id):
    """Check analysis status for a test run"""
    try:
        response = requests.get(f"{API_BASE}/analysis/run/{run_id}/status")
        response.raise_for_status()
        result = response.json()
        
        print_header(f"Analysis Status - Run #{run_id}")
        
        status = result.get('status', 'unknown')
        if status == 'completed':
            print_success(f"Status: {status}")
        elif status == 'in_progress':
            print_info(f"Status: {status}")
        else:
            print(f"Status: {status}")
        
        if result.get('clusters_count'):
            print(f"Clusters found: {result['clusters_count']}")
        
    except requests.exceptions.RequestException as e:
        print_error(f"Failed to check status: {e}")
        sys.exit(1)

def view_clusters(run_id):
    """View failure clusters for a test run"""
    try:
        response = requests.get(f"{API_BASE}/analysis/run/{run_id}/clusters")
        response.raise_for_status()
        clusters = response.json()
        
        if not clusters:
            print_info("No clusters found. Run AI analysis first.")
            return
        
        print_header(f"Failure Clusters - Run #{run_id}")
        
        for i, cluster in enumerate(clusters, 1):
            severity_color = {
                'Critical': Colors.RED,
                'High': Colors.YELLOW,
                'Medium': Colors.BLUE,
                'Low': Colors.GREEN
            }.get(cluster.get('severity', 'Low'), Colors.ENDC)
            
            print(f"\n{Colors.BOLD}Cluster #{cluster['id']}{Colors.ENDC}")
            print(f"Severity: {severity_color}{cluster.get('severity', 'N/A')}{Colors.ENDC}")
            print(f"Category: {cluster.get('category', 'N/A')}")
            print(f"Failures: {cluster.get('failures_count', 0)}")
            
            if cluster.get('ai_summary'):
                summary_lines = cluster['ai_summary'].split('\n')
                print(f"Summary: {summary_lines[0][:80]}...")
            
            if cluster.get('redmine_issue_id'):
                print(f"{Colors.GREEN}Redmine Issue: #{cluster['redmine_issue_id']}{Colors.ENDC}")
        
    except requests.exceptions.RequestException as e:
        print_error(f"Failed to fetch clusters: {e}")
        sys.exit(1)

def delete_run(run_id):
    """Delete a test run"""
    print(f"{Colors.YELLOW}⚠ Warning: This will permanently delete run #{run_id}{Colors.ENDC}")
    confirm = input("Type 'yes' to confirm: ")
    
    if confirm.lower() != 'yes':
        print_info("Deletion cancelled")
        return
    
    try:
        response = requests.delete(f"{API_BASE}/reports/runs/{run_id}")
        response.raise_for_status()
        
        print_success(f"Run #{run_id} deleted successfully")
        
    except requests.exceptions.RequestException as e:
        print_error(f"Failed to delete run: {e}")
        sys.exit(1)

def print_usage():
    """Print usage information"""
    print(__doc__)

def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == 'list':
        list_runs()
    elif command == 'count':
        count_runs()
    elif command == 'details':
        if len(sys.argv) < 3:
            print_error("Usage: gms-cli.py details <run_id>")
            sys.exit(1)
        get_run_details(sys.argv[2])
    elif command == 'upload':
        if len(sys.argv) < 3:
            print_error("Usage: gms-cli.py upload <xml_file>")
            sys.exit(1)
        upload_file(sys.argv[2])
    elif command == 'analyze':
        if len(sys.argv) < 3:
            print_error("Usage: gms-cli.py analyze <run_id>")
            sys.exit(1)
        run_analysis(sys.argv[2])
    elif command == 'status':
        if len(sys.argv) < 3:
            print_error("Usage: gms-cli.py status <run_id>")
            sys.exit(1)
        check_status(sys.argv[2])
    elif command == 'clusters':
        if len(sys.argv) < 3:
            print_error("Usage: gms-cli.py clusters <run_id>")
            sys.exit(1)
        view_clusters(sys.argv[2])
    elif command == 'delete':
        if len(sys.argv) < 3:
            print_error("Usage: gms-cli.py delete <run_id>")
            sys.exit(1)
        delete_run(sys.argv[2])
    elif command in ['help', '-h', '--help']:
        print_usage()
    else:
        print_error(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)

if __name__ == "__main__":
    main()
