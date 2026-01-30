# CTS Insight - Software Architecture & Design (v2.0)

**Last Updated:** 2026-01-20
**Status:** Active / Production

This document provides a comprehensive overview of the CTS Insight's software architecture, reflecting the latest state of the codebase including **Client-Side Parsing**, **Multi-LLM Support (Cambrian/Internal)**, and **Redmine Integration**.

## 🏗️ High-Level Architecture

The system enables Hybrid Processing: heavy XML parsing is offloaded to the client (Web Worker), while AI integration and data persistence are handled by the backend.

```mermaid
graph TB
    subgraph "Client Layer"
        Browser["Web Browser"]
        Worker["Web Worker<br/>(XML Parsing)"]
    end
    
    subgraph "Application Layer"
        Nginx["Nginx<br/>(Reverse Proxy)"]
        FastAPI["FastAPI Application<br/>(Python)"]
    end
    
    subgraph "Business Logic Layer"
        LegacyUpload["Server-Side Upload<br/>(Legacy)"]
        Import["JSON Importer<br/>(Optimized)"]
        Analysis["AI Analysis Engine"]
        Clustering["Failure Clustering"]
        Redmine["Redmine Integration"]
    end
    
    subgraph "Data Layer"
        SQLite["SQLite Database<br/>(gms_analysis.db)"]
    end
    
    subgraph "External Services"
        OpenAI["OpenAI API"]
        Cambrian["Cambrian LLM<br/>(Internal)"]
        LocalLLM["Local Llama"]
        RedmineServer["Redmine Server"]
    end
    
    Browser -->|Select File| Worker
    Worker -->|JSON Data| Browser
    Browser -->|HTTPS| Nginx
    Nginx --> FastAPI
    
    FastAPI --> Import
    FastAPI --> LegacyUpload
    FastAPI --> Analysis
    FastAPI --> Clustering
    FastAPI --> Redmine
    
    Import --> SQLite
    LegacyUpload --> SQLite
    
    Analysis --> OpenAI
    Analysis --> Cambrian
    Analysis --> LocalLLM
    Analysis --> SQLite
    Clustering --> SQLite
    
    Redmine --> RedmineServer
    Redmine --> SQLite
    
    style Browser fill:#e1f5ff
    style Worker fill:#e1f5ff
    style FastAPI fill:#fff4e1
    style SQLite fill:#e8f5e9
    style Cambrian fill:#fce4ec
```

## 📦 Component Architecture

```mermaid
graph LR
    subgraph "Frontend (Single Page App)"
        HTML["index.html"]
        JS["app.js<br/>(Router & UI)"]
        Worker["xml-parser.worker.js<br/>(Background Thread)"]
        CSS["Tailwind CSS"]
    end
    
    subgraph "Backend API (FastAPI)"
        Main["main.py"]
        
        subgraph "Routers"
            UploadRouter["upload.py"]
            ImportRouter["import_json.py"]
            ReportsRouter["reports.py"]
            AnalysisRouter["analysis.py"]
            SettingsRouter["settings.py"]
            IntegrationsRouter["integrations.py"]
        end
        
        subgraph "Services"
            LLMClient["llm_client.py<br/>(OpenAI/Cambrian)"]
            ClusterEngine["clustering.py"]
            SubmissionService["submission_service.py<br/>(Grouping Logic)"]
            RedmineClient["redmine_client.py"]
        end
        
        subgraph "Data Model"
            Models["models.py"]
            Database["database.py"]
        end
    end
    
    HTML --> JS
    JS --> Worker
    JS --> Main
    
    Main --> UploadRouter
    Main --> ImportRouter
    Main --> AnalysisRouter
    
    AnalysisRouter --> LLMClient
    AnalysisRouter --> ClusterEngine
    IntegrationsRouter --> RedmineClient
    
    LLMClient --> Models
    ClusterEngine --> Models
    Models --> Database
    
    style JS fill:#e1f5ff
    style Worker fill:#e1f5ff
```

## 🔄 Data Flow: Smart Import (Optimized)
Instead of uploading GB-sized XML files, the browser parses them locally and sends only relevant failure data.

```mermaid
sequenceDiagram
    participant User
    participant Browser
    participant Worker as Web Worker
    participant FastAPI
    participant Database

    User->>Browser: Select Test Result (XML)
    Browser->>Worker: Post Message (File Blob)
    
    loop Streaming Parse
        Worker->>Worker: Parse XML Nodes
        Worker->>Worker: Filter "fail" results
        Worker-->>Browser: Progress %
    end
    
    Worker-->>Browser: Complete JSON Payload
    Browser->>FastAPI: POST /api/import (JSON)
    FastAPI->>Database: Batch Insert TestRun
    FastAPI->>Database: Batch Insert TestCases (Failures Only)
    Database-->>FastAPI: new_run_id
    FastAPI-->>Browser: {test_run_id: 123, status: "ok"}
    Browser-->>User: Navigate to Run Details
```

## 🧠 AI Analysis & Clustering Flow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Clustering
    participant LLMSelector
    participant Providers
    participant DB

    User->>API: Trigger Analysis (Run 123)
    API->>Clustering: Group Failures (DBSCAN/Levenshtein)
    Clustering->>DB: Create FailureClusters
    
    loop For Each Cluster
        Clustering->>LLMSelector: Request Analysis
        LLMSelector->>DB: Check Settings (Provider)
        db-->>LLMSelector: "cambrian"
        
        LLMSelector->>Providers: Call Cambrian API
        Providers-->>LLMSelector: {RootCause, Solution, Severity}
        LLMSelector->>DB: Update FailureCluster
    end
    
    API-->>User: Analysis Complete
```

## 🗄️ Database Schema (SQLite)

Key tables designed for efficient storage of failures. Passing tests are only aggregated.

```mermaid
erDiagram
    TestRun ||--o{ TestCase : contains
    TestCase ||--|{ FailureAnalysis : has
    FailureAnalysis }o--|| FailureCluster : belongs_to
    Settings {
        string llm_provider "openai | internal | cambrian"
        string cambrian_url
        string cambrian_model
    }
    
    TestRun {
        int id PK
        string test_suite_name
        int failed_tests
        int passed_tests
        string device_fingerprint
    }
    
    TestCase {
        int id PK
        string module_name
        string method_name
        text stack_trace
        text error_message
    }
    
    FailureCluster {
        int id PK
        text signature
        text ai_summary
        string severity
        int redmine_issue_id
    }
```

## 📁 Directory Structure (2026)

```
GMS-helper/
├── backend/
│   ├── main.py                 # App Entry
│   ├── analysis/               # AI & ML Logic
│   │   ├── clustering.py       # Stack Trace Clustering usage
│   │   └── llm_client.py       # Multi-provider LLM Client
│   │   ├── database.py         # DB Connect
│   │   └── models.py           # SQL Models (TestRun, TestCase)
│   ├── services/               # Shared Business Logic
│   │   └── submission_service.py # Centralized Grouping Logic
│   ├── routers/                # REST Controllers
│   │   ├── analysis.py         # Analysis Endpoints
│   │   ├── import_json.py      # Client-side ingest endpoint
│   │   ├── integrations.py     # Redmine/Jira
│   │   ├── reports.py          # Read-only run data
│   │   └── settings.py         # LLM Config
│   └── static/                 # Frontend Assets
│       ├── app.js              # SPA Logic
│       ├── index.html          # Entry HTML
│       └── xml-parser.worker.js # Background Parser
├── docs/                       # Project Documentation
└── gms_analysis.db            # Local Database
```

## 🚀 Deployment

The system is deployed via Docker Compose containing:
1.  **Backend**: Uvicorn running FastAPI.
2.  **Frontend**: Nginx serving static files and reverse-proxying API.

### Environment variables
*   `DATABASE_URL`: Path to SQLite DB.
*   `OPENAI_API_KEY`: (Optional) for OpenAI.
*   `CAMBRIAN_TOKEN`: (Optional) for Internal LLM.
## 📄 Supplementary Documents
*   [Submission Grouping Design](SUBMISSION_GROUPING_DESIGN.md) - Detailed logic for test run auto-grouping.
*   [AI Analysis Design](LLM_INTEGRATION_DESIGN.md) - Deep dive into LLM integration.
