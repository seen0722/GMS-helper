# CTS Insight Wiki

Welcome to the **CTS Insight** project wiki! This tool is designed to streamline the analysis of Android GMS (Google Mobile Services) certification test results (CTS, GTS, VTS, STS).

## 🚀 Project Overview

CTS Insight is a web-based application that parses XML test results, provides a dashboard for visualization, and leverages AI to analyze failures and cluster them by root cause. It also integrates with Redmine for issue tracking.

### Key Features

*   **📊 Dashboard**: Visual overview of test runs, pass/fail rates, and trends.
*   **🤖 AI Analysis**: Uses OpenAI (GPT-4) to analyze failure stack traces, identify root causes, and suggest solutions.
*   **🧩 Failure Clustering**: Automatically groups thousands of similar failures into manageable clusters using TF-IDF and K-Means algorithms.
*   **🐞 Redmine Integration**: One-click issue creation in Redmine, supporting bulk creation for failure clusters.
*   **📂 Large File Support**: Handles large XML result files (GBs in size) efficiently.
*   **🔒 Secure**: Encrypted storage for API keys and sensitive settings.

---

## 🏗️ System Architecture

The application follows a modern 3-tier architecture:

*   **Frontend**: Vanilla JavaScript (SPA) + Tailwind CSS. Fast, lightweight, and responsive.
*   **Backend**: Python FastAPI. High-performance, async API handling.
*   **Database**: SQLite (Embedded). Simple, portable, and efficient for this use case.
*   **AI Engine**: OpenAI GPT-4o-mini for analysis + Scikit-learn for clustering.

> For detailed architecture diagrams, please refer to [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 🛠️ Installation & Deployment

We support deploying to **Vultr VPS** with **Cloudflare** for DNS and security.

### Quick Start (Vultr)

1.  **Provision VPS**: Ubuntu 22.04 LTS.
2.  **Run Script**:
    ```bash
    curl -o deploy.sh https://raw.githubusercontent.com/seen0722/GMS-helper/main/deploy_vultr.sh
    chmod +x deploy.sh
    ./deploy.sh
    ```
3.  **Configure**: Set up your OpenAI API Key in the web UI.

### Docker Quick Start

```bash
docker run -d -p 8000:8000 -v $(pwd)/data:/app/data seen0516/gms-helper:latest
```

> For the complete deployment guide, including SSL and Cloudflare setup, see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## 📖 User Guide

### 1. Uploading Test Results
*   Navigate to the **Upload** page.
*   Drag and drop your `test_result.xml` file (supports `.zip` containing XML as well).
*   Wait for parsing to complete.

### 2. Analyzing Failures
*   Open a Test Run.
*   Click **"Run AI Analysis"**.
*   The system will cluster failures and provide an AI-generated summary for each cluster.

### 3. Reporting Bugs (Redmine)
*   In the **Clusters** view, review the AI analysis.
*   Click **"Create Issue"** to file a bug in Redmine.
*   The issue description will be pre-filled with the AI summary and stack traces.

---

## 🔌 API Documentation

The backend provides a RESTful API for automation and integration.

**Base URL**: `https://gms.zmlab.io/api`

### Common Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/upload/` | Upload a test result XML file |
| `GET` | `/reports/runs` | List all test runs |
| `GET` | `/reports/runs/{id}` | Get details of a specific run |
| `POST` | `/analysis/run/{id}` | Trigger AI analysis for a run |

> For detailed API usage examples (cURL, Python), see [API_USAGE.md](API_USAGE.md).

---

## 🧠 AI Engine Details

The AI engine is the core of this project. It works in two stages:

1.  **Clustering (HDBSCAN)**:
    *   **Algorithm**: Domain-Aware Feature Engineering + HDBSCAN (Hierarchical Density-Based Clustering).
    *   **Key Features**: Module/class weighting, exception extraction, framework frame filtering.
    *   **Purpose**: Groups failures into pure clusters with automatic cluster count discovery.
    *   **Quality**: 100% purity, Silhouette score ≥ 0.7, outlier handling via module-based fallback.
    
2.  **Analysis (LLM)**:
    *   **Model**: OpenAI GPT-4o-mini (or internal LLM gateway).
    *   **Purpose**: Analyzes each cluster to determine **Root Cause**, **Solution**, **Severity**, and **Category**.

> Learn more about the AI implementation in [AI_ANALYSIS.md](AI_ANALYSIS.md).

---

## 💻 Development

### Prerequisites
*   Python 3.10+
*   Node.js (optional, for frontend tooling)

### Local Setup
```bash
# 1. Clone repo
git clone https://github.com/seen0722/GMS-helper.git

# 2. Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Run server
uvicorn backend.main:app --reload
```

---

## 🤝 Contributing

Please read `CONTRIBUTING.md` (if available) for details on our code of conduct, and the process for submitting pull requests to us.

---

*Last updated: 2026-01-15*
