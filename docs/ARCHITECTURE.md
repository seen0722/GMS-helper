# GMS Certification Analyzer - Software Architecture

This document provides a comprehensive overview of the GMS Certification Analyzer's software architecture.

## 🏗️ High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        Browser["Web Browser"]
        CLI["CLI/API Clients"]
    end
    
    subgraph "Application Layer"
        Nginx["Nginx<br/>(Reverse Proxy)"]
        FastAPI["FastAPI Application<br/>(Python)"]
    end
    
    subgraph "Business Logic Layer"
        Parser["XML Parser<br/>(CTS/GTS/VTS/STS)"]
        Analysis["AI Analysis Engine<br/>(OpenAI)"]
        Clustering["Failure Clustering"]
        Redmine["Redmine Integration"]
    end
    
    subgraph "Data Layer"
        SQLite["SQLite Database<br/>(gms_analysis.db)"]
        Files["File Storage<br/>(uploads/)"]
    end
    
    subgraph "External Services"
        OpenAI["OpenAI API"]
        RedmineServer["Redmine Server"]
    end
    
    Browser --> Nginx
    CLI --> Nginx
    Nginx --> FastAPI
    FastAPI --> Parser
    FastAPI --> Analysis
    FastAPI --> Clustering
    FastAPI --> Redmine
    Parser --> SQLite
    Analysis --> OpenAI
    Analysis --> SQLite
    Clustering --> SQLite
    Redmine --> RedmineServer
    Redmine --> SQLite
    FastAPI --> Files
    
    style Browser fill:#e1f5ff
    style FastAPI fill:#fff4e1
    style SQLite fill:#e8f5e9
    style OpenAI fill:#fce4ec
    style RedmineServer fill:#fce4ec
```

## 📦 Component Architecture

```mermaid
graph LR
    subgraph "Frontend (Static)"
        HTML["index.html"]
        JS["app.js<br/>(Vanilla JS)"]
        CSS["Tailwind CSS"]
    end
    
    subgraph "Backend API (FastAPI)"
        Main["main.py<br/>(Entry Point)"]
        
        subgraph "Routers"
            Upload["upload.py"]
            Reports["reports.py"]
            AnalysisRouter["analysis.py"]
            Settings["settings.py"]
            Integrations["integrations.py"]
            System["system.py"]
        end
        
        subgraph "Core Services"
            XMLParser["xml_parser.py"]
            LLMClient["llm_client.py"]
            ClusterEngine["clustering.py"]
            RedmineClient["redmine_client.py"]
        end
        
        subgraph "Data Layer"
            Models["models.py"]
            Database["database.py"]
            Encryption["encryption.py"]
        end
    end
    
    HTML --> JS
    JS --> Main
    Main --> Upload
    Main --> Reports
    Main --> AnalysisRouter
    Main --> Settings
    Main --> Integrations
    Main --> System
    
    Upload --> XMLParser
    AnalysisRouter --> LLMClient
    AnalysisRouter --> ClusterEngine
    Integrations --> RedmineClient
    
    XMLParser --> Models
    LLMClient --> Models
    ClusterEngine --> Models
    RedmineClient --> Models
    Models --> Database
    Settings --> Encryption
    
    style HTML fill:#e1f5ff
    style Main fill:#fff4e1
    style Models fill:#e8f5e9
```

## 🔄 Data Flow - Upload & Analysis

```mermaid
sequenceDiagram
    participant User
    participant Browser
    participant FastAPI
    participant Parser
    participant Database
    participant AI
    participant Clustering
    
    User->>Browser: Upload XML file
    Browser->>FastAPI: POST /api/upload/
    FastAPI->>Parser: Parse XML
    Parser->>Parser: Extract test cases
    Parser->>Database: Store test run & cases
    Database-->>FastAPI: Return test_run_id
    FastAPI-->>Browser: {"test_run_id": 5}
    Browser-->>User: Show run details
    
    User->>Browser: Click "Run AI Analysis"
    Browser->>FastAPI: POST /api/analysis/run/5
    FastAPI->>AI: Analyze failures
    AI->>AI: Generate summaries
    AI-->>FastAPI: Return analysis
    FastAPI->>Clustering: Cluster failures
    Clustering->>Database: Store clusters
    Database-->>FastAPI: Confirm
    FastAPI-->>Browser: Analysis complete
    Browser-->>User: Show clusters
```

## 🎯 Redmine Integration Flow

```mermaid
sequenceDiagram
    participant User
    participant Browser
    participant FastAPI
    participant Database
    participant Redmine
    
    User->>Browser: Click "Assign to Redmine"
    Browser->>FastAPI: GET /api/integrations/redmine/projects
    FastAPI->>Redmine: Fetch projects
    Redmine-->>FastAPI: Return projects
    FastAPI-->>Browser: Display projects
    
    User->>Browser: Fill form & click "Create Issue"
    Browser->>FastAPI: POST /api/integrations/redmine/issue
    FastAPI->>Redmine: Create issue
    Redmine-->>FastAPI: Return issue details
    FastAPI->>Database: Link cluster to issue
    Database-->>FastAPI: Confirm
    FastAPI-->>Browser: Success
    Browser-->>User: Show linked issue
```

## 🗄️ Database Schema

```mermaid
erDiagram
    TestRun ||--o{ TestCase : contains
    TestCase ||--o| FailureAnalysis : has
    FailureAnalysis }o--|| FailureCluster : belongs_to
    FailureCluster ||--o| RedmineIssue : linked_to
    
    TestRun {
        int id PK
        string test_suite_name
        string device_fingerprint
        string build_id
        int total_tests
        int passed_tests
        int failed_tests
        datetime created_at
        string status
        string analysis_status
    }
    
    TestCase {
        int id PK
        int test_run_id FK
        string module_name
        string class_name
        string method_name
        string status
        text error_message
        text stack_trace
    }
    
    FailureAnalysis {
        int id PK
        int test_case_id FK
        int cluster_id FK
        text ai_analysis
        float confidence_score
    }
    
    FailureCluster {
        int id PK
        text ai_summary
        text common_root_cause
        text common_solution
        string severity
        string category
        int redmine_issue_id
        float confidence_score
    }
    
    Settings {
        int id PK
        string openai_api_key
        string redmine_url
        string redmine_api_key
    }
```

## 📁 Directory Structure

```
GMS-helper/
├── backend/
│   ├── main.py                 # FastAPI application entry
│   ├── routers/                # API endpoints
│   │   ├── upload.py          # File upload handling
│   │   ├── reports.py         # Test run reports
│   │   ├── analysis.py        # AI analysis
│   │   ├── integrations.py    # Redmine integration
│   │   ├── settings.py        # Configuration
│   │   └── system.py          # System operations
│   ├── parser/                 # XML parsers
│   │   ├── base_parser.py     # Base parser class
│   │   └── xml_parser.py      # XML implementation
│   ├── analysis/               # AI & clustering
│   │   ├── llm_client.py      # OpenAI client
│   │   └── clustering.py      # Failure clustering
│   ├── integrations/           # External services
│   │   └── redmine_client.py  # Redmine API client
│   ├── database/               # Data layer
│   │   ├── database.py        # SQLAlchemy setup
│   │   └── models.py          # ORM models
│   ├── utils/                  # Utilities
│   │   └── encryption.py      # API key encryption
│   └── static/                 # Frontend files
│       ├── index.html         # Main UI
│       └── app.js             # Frontend logic
├── uploads/                    # Uploaded XML files
├── gms_analysis.db            # SQLite database
└── requirements.txt           # Python dependencies
```

## 🔐 Security Architecture

```mermaid
graph TB
    subgraph "Security Layers"
        SSL["SSL/TLS<br/>(HTTPS)"]
        Firewall["UFW Firewall"]
        Nginx["Nginx<br/>(Rate Limiting)"]
        
        subgraph "Application Security"
            Encryption["Fernet Encryption<br/>(API Keys)"]
            Validation["Input Validation"]
            CORS["CORS Policy"]
        end
        
        subgraph "External Security"
            CloudflareDNS["Cloudflare DNS"]
            CloudflareProxy["Cloudflare Proxy<br/>(Optional)"]
        end
    end
    
    Internet["Internet"] --> CloudflareDNS
    CloudflareDNS --> CloudflareProxy
    CloudflareProxy --> SSL
    SSL --> Firewall
    Firewall --> Nginx
    Nginx --> Validation
    Validation --> Encryption
    
    style SSL fill:#e8f5e9
    style Encryption fill:#e8f5e9
    style Firewall fill:#fff4e1
```

## 🚀 Deployment Architecture

```mermaid
graph TB
    subgraph "Development"
        DevLocal["Local Machine<br/>(localhost:8000)"]
    end
    
    subgraph "Version Control"
        GitHub["GitHub Repository<br/>(seen0722/GMS-helper)"]
    end
    
    subgraph "Production (Vultr VPS)"
        subgraph "System Services"
            Supervisor["Supervisor<br/>(Process Manager)"]
            NginxProd["Nginx<br/>(Port 80/443)"]
            UFW["UFW Firewall"]
        end
        
        subgraph "Application"
            Uvicorn["Uvicorn<br/>(ASGI Server)"]
            FastAPIProd["FastAPI App<br/>(Port 8000)"]
        end
        
        subgraph "Data"
            SQLiteProd["SQLite DB"]
            UploadsProd["Uploads Directory"]
        end
    end
    
    subgraph "DNS & CDN"
        Cloudflare["Cloudflare<br/>(DNS + SSL)"]
    end
    
    DevLocal -->|git push| GitHub
    GitHub -->|git pull| FastAPIProd
    
    Cloudflare -->|HTTPS| NginxProd
    UFW --> NginxProd
    NginxProd -->|Reverse Proxy| Uvicorn
    Supervisor -->|Manages| Uvicorn
    Uvicorn --> FastAPIProd
    FastAPIProd --> SQLiteProd
    FastAPIProd --> UploadsProd
    
    style GitHub fill:#e1f5ff
    style Cloudflare fill:#fff4e1
    style FastAPIProd fill:#e8f5e9
```

## 🔄 Request Processing Flow

```mermaid
flowchart TD
    Start([User Request]) --> DNS{DNS Resolution}
    DNS -->|Cloudflare| SSL[SSL Termination]
    SSL --> Nginx[Nginx Reverse Proxy]
    Nginx --> Route{Route Type?}
    
    Route -->|Static Files| Static[Serve HTML/JS/CSS]
    Route -->|API Call| FastAPI[FastAPI Router]
    
    FastAPI --> Auth{Authentication<br/>Required?}
    Auth -->|No| Handler[Route Handler]
    Auth -->|Yes| CheckAuth{Valid?}
    CheckAuth -->|No| Error401[401 Unauthorized]
    CheckAuth -->|Yes| Handler
    
    Handler --> Process{Processing Type}
    Process -->|Upload| ParseXML[Parse XML]
    Process -->|Analysis| RunAI[Run AI Analysis]
    Process -->|Report| QueryDB[Query Database]
    Process -->|Redmine| CallRedmine[Call Redmine API]
    
    ParseXML --> SaveDB[(Save to Database)]
    RunAI --> SaveDB
    QueryDB --> SaveDB
    CallRedmine --> SaveDB
    
    SaveDB --> Response[Generate Response]
    Static --> Response
    Error401 --> Response
    
    Response --> End([Return to User])
    
    style Start fill:#e1f5ff
    style End fill:#e8f5e9
    style FastAPI fill:#fff4e1
```

## 📊 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | HTML5, Vanilla JavaScript, Tailwind CSS | User interface |
| **Backend** | Python 3.8+, FastAPI, Uvicorn | API server |
| **Database** | SQLite, SQLAlchemy | Data persistence |
| **AI/ML** | OpenAI GPT-4 | Failure analysis & clustering |
| **Integration** | Redmine REST API | Issue tracking |
| **Web Server** | Nginx | Reverse proxy, SSL termination |
| **Process Manager** | Supervisor | Application lifecycle |
| **Deployment** | Vultr VPS, Ubuntu 22.04 | Hosting |
| **DNS/CDN** | Cloudflare | DNS, SSL, DDoS protection |
| **Security** | Fernet encryption, Let's Encrypt | API key encryption, SSL |

## 🎨 Frontend Architecture

```mermaid
graph LR
    subgraph "Single Page Application"
        Router["Client-Side Router"]
        
        subgraph "Pages"
            Dashboard["Dashboard"]
            Upload["Upload"]
            RunDetails["Run Details"]
            Settings["Settings"]
        end
        
        subgraph "Components"
            FailureTable["Failure Table"]
            ClusterView["Cluster View"]
            RedmineModal["Redmine Modal"]
            Charts["Statistics Charts"]
        end
        
        subgraph "Services"
            API["API Client"]
            State["State Management"]
        end
    end
    
    Router --> Dashboard
    Router --> Upload
    Router --> RunDetails
    Router --> Settings
    
    Dashboard --> Charts
    RunDetails --> FailureTable
    RunDetails --> ClusterView
    ClusterView --> RedmineModal
    
    Dashboard --> API
    Upload --> API
    RunDetails --> API
    Settings --> API
    
    API --> State
    
    style Router fill:#e1f5ff
    style API fill:#fff4e1
```

## 🔌 API Architecture

```mermaid
graph TB
    subgraph "API Endpoints"
        subgraph "Upload API"
            UploadEndpoint["/api/upload/"]
        end
        
        subgraph "Reports API"
            ListRuns["/api/reports/runs"]
            GetRun["/api/reports/runs/{id}"]
            GetStats["/api/reports/runs/{id}/stats"]
            GetFailures["/api/reports/runs/{id}/failures"]
        end
        
        subgraph "Analysis API"
            StartAnalysis["/api/analysis/run/{id}"]
            GetStatus["/api/analysis/run/{id}/status"]
            GetClusters["/api/analysis/run/{id}/clusters"]
        end
        
        subgraph "Integrations API"
            GetProjects["/api/integrations/redmine/projects"]
            CreateIssue["/api/integrations/redmine/issue"]
            LinkIssue["/api/integrations/redmine/link"]
            BulkCreate["/api/integrations/redmine/bulk-create"]
        end
        
        subgraph "Settings API"
            GetSettings["/api/settings/redmine"]
            SaveSettings["/api/settings/redmine"]
        end
    end
    
    style UploadEndpoint fill:#e1f5ff
    style StartAnalysis fill:#fff4e1
    style CreateIssue fill:#e8f5e9
```

## 📈 Scalability Considerations

### Current Architecture (Single Server)
- **Suitable for**: Small to medium teams
- **Capacity**: ~100 test runs/day
- **Concurrent users**: ~10-20

### Future Scaling Options

```mermaid
graph TB
    subgraph "Horizontal Scaling"
        LB["Load Balancer"]
        App1["App Server 1"]
        App2["App Server 2"]
        App3["App Server 3"]
        SharedDB["Shared Database<br/>(PostgreSQL)"]
        Redis["Redis Cache"]
    end
    
    LB --> App1
    LB --> App2
    LB --> App3
    App1 --> SharedDB
    App2 --> SharedDB
    App3 --> SharedDB
    App1 --> Redis
    App2 --> Redis
    App3 --> Redis
    
    style LB fill:#e1f5ff
    style SharedDB fill:#e8f5e9
```

---

## 🎯 Key Design Principles

1. **Separation of Concerns**: Clear boundaries between parsing, analysis, and integration
2. **RESTful API**: Standard HTTP methods and status codes
3. **Asynchronous Processing**: Background tasks for long-running operations
4. **Encryption**: Sensitive data encrypted at rest
5. **Stateless**: API is stateless for easy scaling
6. **Single Page Application**: Fast, responsive UI without page reloads

## 📝 Summary

The GMS Certification Analyzer follows a **three-tier architecture**:
- **Presentation Layer**: Web browser with vanilla JavaScript
- **Application Layer**: FastAPI with modular routers
- **Data Layer**: SQLite with SQLAlchemy ORM

This architecture provides:
- ✅ **Simplicity**: Easy to understand and maintain
- ✅ **Modularity**: Components can be updated independently
- ✅ **Extensibility**: New features can be added easily
- ✅ **Security**: Multiple layers of protection
- ✅ **Scalability**: Can be scaled horizontally when needed
